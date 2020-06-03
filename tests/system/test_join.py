import datetime
import functools
import re
from functools import partial
from unittest import TestCase
from unittest.mock import patch

import responses
from aioresponses import aioresponses, CallbackResult

from dimensigon import join, Gate, token as generate_token, Locker, User
from dm.domain.entities import Server, Dimension, Catalog
from dm.utils.helpers import generate_dimension
from dm.web import create_app, db


class TestApi(TestCase):

    @patch('dm.domain.entities.get_now')
    def setUp(self, mock_now):
        """Create and configure a new app instance for each test."""
        mock_now.return_value = datetime.datetime(2019, 4, 1)
        # create the app with common test config
        self.app_join = create_app('test')
        self.app_join.config['SECURIZER'] = True
        self.app_join.config['SERVER_NAME'] = 'new'
        with self.app_join.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()
            Server.set_initial()
            me = Server.get_current()
            # remove Gates
            [db.session.delete(g) for g in me.gates]
            Gate(me, port=8000, dns='new')
            db.session.commit()
            self.server_new = Server.get_current().to_json()

        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'node1'
        self.app.config['SECURIZER'] = True
        mock_now.return_value = datetime.datetime(2019, 3, 1)
        with self.app.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()
            Server.set_initial()
            me = Server.get_current()
            # remove Gates
            [db.session.delete(g) for g in me.gates]
            Gate(me, port=8000, dns='node1')
            db.session.commit()
            dim = generate_dimension('test')
            dim.current = True
            db.session.add(dim)
            db.session.commit()
            self.dimension = dim.to_json()
            self.server_node1 = Server.get_current().to_json()

        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app_join.app_context():
            db.session.remove()
            db.drop_all()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('dm.domain.entities.route.check_host')
    @patch('dm.domain.entities.get_now')
    # @patch('dimensigon.rsa.newkeys')
    @aioresponses()
    def test_join_command(self, mock_now, mock_check, m):
        mock_now.return_value = datetime.datetime(2019, 5, 1)

        mock_check.return_value = True

        def callback_client(method, client, url, **kwargs):
            kwargs.pop('allow_redirects')

            func = getattr(client, method.lower())
            r = func(url.path, headers=kwargs['headers'], json=kwargs['json'])

            return CallbackResult(method.upper(), status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('^https?://node1.*'),
               callback=functools.partial(callback_client, 'POST', self.client), repeat=True)

        def request_callback(request, client):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        with responses.RequestsMock() as rsps:
            rsps.add_callback(responses.POST,
                              re.compile('^https?://node1.*'),
                              callback=partial(request_callback, client=self.client))
            rsps.add_callback(responses.GET,
                              re.compile('^https?://node1.*'),
                              callback=partial(request_callback, client=self.client))

            with self.app.app_context():
                runner = self.app.test_cli_runner()
                result = runner.invoke(generate_token, [], catch_exceptions=False)
                token = result.stdout.strip()

            runner = self.app_join.test_cli_runner()

            result = runner.invoke(join, ['--no-ssl', 'node1:5000', token], catch_exceptions=False)

        with self.app.app_context():
            # check if new server created
            server_new = Server.query.get(self.server_new.get('id'))
            self.assertEqual(server_new.last_modified_at, datetime.datetime(2019, 5, 1))
            server_new.last_modified_at = datetime.datetime(2019, 4, 1)
            self.assertDictEqual(self.server_new, server_new.to_json())

        with self.app_join.app_context():
            self.assertDictEqual(self.dimension, Dimension.get_current().to_json())
            s = Server.query.get(self.server_node1.get('id'))
            self.assertEqual(0, s.route.cost)
            self.assertListEqual([('Gate',), ('Server',), ('User',)], db.session.query(Catalog.entity).order_by('entity').all())
            self.assertEqual(datetime.datetime(2019, 5, 1),
                             Catalog.query.filter_by(entity='Server').one().last_modified_at)
