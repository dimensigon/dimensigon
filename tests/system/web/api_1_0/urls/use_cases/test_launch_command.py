import re
import traceback
from functools import partial
from unittest import TestCase, mock

from aioresponses import aioresponses, CallbackResult
from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Server, Route, Dimension, User
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import create_app, db
from dimensigon.web.api_1_0.urls.use_cases import wrap_sudo


class TestLaunchCommand(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        # self.app.config['SECURIZER'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.dim = generate_dimension('test')
        self.dim.current = True
        self.json_dim = self.dim.to_json()
        self.client = self.app.test_client()

        set_initial(server=False)
        User.set_initial()

        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
        server = Server('node1', port=8000, me=True, granules='granule')
        db.session.add_all([server, self.dim])
        db.session.commit()

        # dump data
        self.json_node1 = server.to_json(add_gates=True)
        self.json_users = [u.to_json() for u in User.query.all()]

        self.app2 = create_app('test')
        # self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()
        with self.app2.app_context():
            set_initial(server=False)
            me = Server('node2', port=8000, me=True, granules='granule')
            db.session.add(me)

            src_server = Server.from_json(self.json_node1)
            Route(src_server, cost=0)
            db.session.add(src_server)

            dim = Dimension.from_json(self.json_dim)
            dim.current = True
            db.session.add(dim)

            users = [User.from_json(ju) for ju in self.json_users]
            db.session.add_all(users)

            db.session.commit()

            # dump data
            self.json_node2 = me.to_json(add_gates=True)

        node2 = Server.from_json(self.json_node2)
        Route(node2, cost=0)
        db.session.add(node2)
        db.session.commit()

    def tearDown(self) -> None:
        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def set_callbacks(self, m):
        def callback_client(method, client, url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            func = getattr(client, method.lower())
            try:
                r = func(url.path, headers=kwargs['headers'], json=kwargs['json'])
            except Exception as e:
                return CallbackResult(method.upper(), status=500, body=traceback.format_exc(), headers={})

            return CallbackResult(method.upper(), status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://node2:.*'),
               callback=partial(callback_client, 'POST', self.app2.test_client()), repeat=True)

    @aioresponses()
    @mock.patch('dimensigon.web.api_1_0.urls.use_cases.subprocess.Popen')
    def test_launch_command(self, m, mock_popen):
        self.maxDiff = None
        self.set_callbacks(m)

        popen_mock = mock.MagicMock()
        mock_popen.return_value = popen_mock
        popen_mock.communicate.return_value = ('output', '')
        type(popen_mock).returncode = mock.PropertyMock(return_value=0)

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "hosts": 'all', 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.json_node1['id']: {'stdout': 'output', 'stderr': '', 'returncode': 0},
                              self.json_node2['id']: {'stdout': 'output', 'stderr': '', 'returncode': 0},
                              },
                             resp.get_json())

        self.assertEqual(2, mock_popen.call_count)

        self.assertTupleEqual((wrap_sudo('root', ['ls', '-l']), ), mock_popen.call_args[0])

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "hosts": [self.json_node2['id']], 'timeout': 1},
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.json_node2['id']: {'stdout': 'output', 'stderr': '', 'returncode': 0},
                              },
                             resp.get_json())

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "ls -l", "hosts": self.json_node1['id'], 'timeout': 1},
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual({self.json_node1['id']: {'stdout': 'output', 'stderr': '', 'returncode': 0},
                              },
                             resp.get_json())

    @aioresponses()
    @mock.patch('dimensigon.web.api_1_0.urls.use_cases.subprocess.Popen')
    def test_launch_command_timeout(self, m, mock_popen):
        self.maxDiff = None
        self.set_callbacks(m)

        args = wrap_sudo('root', ['sleep', '10'])
        cmd = 'sleep 10'
        popen_mock = mock.MagicMock()
        mock_popen.return_value = popen_mock
        popen_mock.communicate.side_effect = [TimeoutError, ('', '')]
        type(popen_mock).returncode = mock.PropertyMock(return_value=0)

        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": cmd, "hosts": 'node1', 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(
            {self.json_node1['id']: {'error': f"Command '{wrap_sudo('root', cmd)}' timed out after 1 seconds",
                                     'stdout': '', 'stderr': ''},
             },
            resp.get_json())



    def test_launch_command_rm_recursive(self):
        resp = self.client.post(url_for('api_1_0.launch_command'),
                                json={"command": "rm -fr /folder", "hosts": "all", 'timeout': 1},
                                headers=self.auth.header)

        self.assertEqual(403, resp.status_code)
        self.assertDictEqual({'error': 'rm with recursion is not allowed'},
                             resp.get_json())