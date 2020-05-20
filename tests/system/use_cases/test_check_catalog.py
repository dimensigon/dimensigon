import os
import re
import uuid
from datetime import datetime
from functools import partial
from unittest import TestCase
from unittest.mock import patch

import responses
from aioresponses import aioresponses, CallbackResult
from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon import Software, ActionTemplate, ActionType, SoftwareServerAssociation, Route, Locker
from dm.domain.entities import Server, Dimension, Catalog
from dm.utils.helpers import generate_dimension
from dm.web import create_app, db
from dm.web.background_tasks import update_catalog

basedir = os.path.abspath(os.path.dirname(__file__))


@patch('dm.web.background_tasks.dm_version', '1')
@patch('dm.web.routes.dm.__version__', '1')
class TestLockScopeFullChain(TestCase):

    # @staticmethod
    # def remove_db_files():
    #     with contextlib.suppress(FileNotFoundError):
    #         os.remove(os.path.join(basedir, 'node1.db'))
    #         os.remove(os.path.join(basedir, 'node2.db'))
    #
    # @classmethod
    # def setUpClass(cls) -> None:
    #     cls.remove_db_files()
    #
    # @classmethod
    # def tearDownClass(cls) -> None:
    #     cls.remove_db_files()

    @patch('dm.domain.entities.get_now')
    def setUp(self, mocked_now):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app1 = create_app('test')
        self.app1.config['SECURIZER'] = True
        self.client1 = self.app1.test_client()
        self.app2 = create_app('test')
        self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()

        mocked_now.return_value = datetime(2019, 4, 1)
        with self.app1.app_context():
            db.create_all()
            Locker.set_initial()
            s1 = Server('node1', id='bbbbbbbb-1234-5678-1234-56781234bbb1', port=8000, me=True)
            s2 = Server('node2', id='bbbbbbbb-1234-5678-1234-56781234bbb2', port=8000)
            Route(s2, cost=0)
            db.session.add_all([s1, s2])
            dim = generate_dimension('dimension')
            dim.current = True
            db.session.add(dim)
            db.session.commit()
            self.s1_json = Server.get_current().to_json()
            self.dim_json = dim.to_json()
            self.headers = {"Authorization": f"Bearer {create_access_token('test')}"}

        with self.app2.app_context():
            db.create_all()
            Locker.set_initial()
            s1 = Server('node1', id='bbbbbbbb-1234-5678-1234-56781234bbb1', port=8000)
            Route(s1, cost=0)
            s2 = Server('node2', id='bbbbbbbb-1234-5678-1234-56781234bbb2', port=8000, me=True)
            db.session.add_all([s1, s2])
            db.session.commit()
            dim = Dimension.from_json(self.dim_json)
            dim.current = True
            db.session.add(dim)
            db.session.commit()

        mocked_now.return_value = datetime(2019, 4, 2)
        with self.app1.app_context():
            soft = Software(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'), name='test', version='1',
                            filename='file')
            at = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa2'),
                                name='mkdir', version=1, action_type=ActionType.SHELL, code='mkdir {dir}')
            db.session.add_all([soft, at])
            db.session.commit()
            mocked_now.return_value = datetime(2019, 4, 3)
            ssa = SoftwareServerAssociation(software=soft, server=Server.get_current(), path='/root')
            db.session.add(ssa)
            db.session.commit()
            self.soft_json = soft.to_json()
            self.at_json = at.to_json()

    def tearDown(self) -> None:
        with self.app1.app_context():
            db.session.remove()
            db.drop_all()

        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

    @aioresponses()
    @responses.activate
    def test_check_catalog(self, m):
        def callback_post_client1(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client1.post(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        def callback_get_client1(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client1.get(url.path, headers=kwargs['headers'])

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        def callback_post_client2(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client2.post(url.path, json=kwargs['json'], headers=kwargs['headers'])

            return CallbackResult('POST', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        def callback_get_client2(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client2.get(url.path, headers=self.headers)

            return CallbackResult('GET', status=r.status_code, body=r.data, content_type=r.content_type,
                                  headers=r.headers)

        m.post(re.compile('https?://(127\.0\.0\.1|node2).*'), callback=callback_post_client2, repeat=True)
        m.get(re.compile('https?://(127\.0\.0\.1|node2).*'), callback=callback_get_client2, repeat=True)
        m.post(re.compile('https?://node1'), callback=callback_post_client1, repeat=True)
        m.get(re.compile('https?://node1'), callback=callback_get_client1, repeat=True)

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        responses.add_callback(responses.POST, re.compile('https?://node1.*'),
                               callback=partial(requests_callback_client, self.client1))
        responses.add_callback(responses.GET, re.compile('https?://node1.*'),
                               callback=partial(requests_callback_client, self.client1))
        responses.add_callback(responses.POST, re.compile('https?://127\.0\.0\.1.*'),
                               callback=partial(requests_callback_client, self.client2))
        responses.add_callback(responses.GET, re.compile('https?://127\.0\.0\.1.*'),
                               callback=partial(requests_callback_client, self.client2))

        with self.app2.app_context():
            self.assertListEqual([('Gate',), ('Server',)],
                                 db.session.query(Catalog.entity).order_by(Catalog.entity).all())
            self.assertEqual(datetime(2019, 4, 1), Catalog.query.get('Server').last_modified_at)

        with self.app1.app_context():
            self.assertEqual(5, Catalog.query.count())
            self.assertEqual(datetime(2019, 4, 1), Catalog.query.get('Server').last_modified_at)
            self.assertEqual(datetime(2019, 4, 1), Catalog.query.get('Gate').last_modified_at)
            self.assertEqual(datetime(2019, 4, 2), Catalog.query.get('Software').last_modified_at)
            self.assertEqual(datetime(2019, 4, 3), Catalog.query.get('SoftwareServerAssociation').last_modified_at)
            self.assertEqual(datetime(2019, 4, 2), Catalog.query.get('ActionTemplate').last_modified_at)
            resp = self.client1.get(url_for('root.healthcheck'))

        with self.app2.app_context():
            s = Server.query.filter_by(_me=False).one()
            update_catalog({s: (resp.get_json(), resp.status_code)})

        with self.app2.app_context():
            soft = Software.query.get('aaaaaaaa-1234-5678-1234-56781234aaa1')
            self.assertDictEqual(self.soft_json, soft.to_json())
            soft = ActionTemplate.query.get('aaaaaaaa-1234-5678-1234-56781234aaa2')
            self.assertDictEqual(self.at_json, soft.to_json())

            self.assertEqual(5, Catalog.query.count())
            self.assertEqual(datetime(2019, 4, 2), Catalog.query.get('Software').last_modified_at)
            self.assertEqual(datetime(2019, 4, 3), Catalog.query.get('SoftwareServerAssociation').last_modified_at)
            self.assertEqual(datetime(2019, 4, 2), Catalog.query.get('ActionTemplate').last_modified_at)
            self.assertEqual(datetime(2019, 4, 1), Catalog.query.get('Server').last_modified_at)
            self.assertEqual(datetime(2019, 4, 1), Catalog.query.get('Gate').last_modified_at)
