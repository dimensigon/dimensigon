import datetime as dt
import os
from unittest import TestCase
from unittest.mock import patch

import responses
from aioresponses import aioresponses
from flask import url_for
from flask_jwt_extended import create_access_token, verify_jwt_in_request

from dimensigon import defaults
from dimensigon.__main__ import Software, ActionTemplate, ActionType, SoftwareServerAssociation, Route, User, Locker
from dimensigon.domain.entities import Server, Dimension, Catalog
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import create_app, db
from dimensigon.web.background_tasks import update_catalog
from dimensigon.web.network import Response
from tests.helpers import set_callbacks

basedir = os.path.abspath(os.path.dirname(__file__))


@patch('dimensigon.web.background_tasks.dm_version', '1')
@patch('dimensigon.web.routes.dimensigon.__version__', '1')
class TestUpdateCatalog(TestCase):

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

    @patch('dimensigon.domain.entities.get_now')
    def setUp(self, mocked_now):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app1 = create_app('test')
        self.app1.config['SECURIZER'] = True
        self.client1 = self.app1.test_client()
        self.app2 = create_app('test')
        self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()

        mocked_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        with self.app1.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()
            self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
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
            self.headers = {"Authorization": f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

        with self.app2.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()
            s1 = Server('node1', id='bbbbbbbb-1234-5678-1234-56781234bbb1', port=8000)
            Route(s1, cost=0)
            s2 = Server('node2', id='bbbbbbbb-1234-5678-1234-56781234bbb2', port=8000, me=True)
            db.session.add_all([s1, s2])
            db.session.commit()
            dim = Dimension.from_json(self.dim_json)
            dim.current = True
            db.session.add(dim)
            db.session.commit()

        mocked_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        with self.app1.app_context():
            soft = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='test', version='1',
                            filename='file')
            at = ActionTemplate(id='aaaaaaaa-1234-5678-1234-56781234aaa2',
                                name='mkdir', version=1, action_type=ActionType.SHELL, code='mkdir {dir}')
            db.session.add_all([soft, at])
            db.session.commit()
            mocked_now.return_value = dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc)
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

        set_callbacks([("node1", self.client1), (r"(127\.0\.0\.1|node2)", self.client2)], m)

        with self.app2.app_context():
            self.assertListEqual([('Gate',), ('Server',), ('User',)],
                                 db.session.query(Catalog.entity).order_by(Catalog.entity).all())
            self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Server').last_modified_at)

        with self.app1.app_context():
            self.assertEqual(6, Catalog.query.count())
            self.assertEqual(defaults.INITIAL_DATEMARK, Catalog.query.get('User').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Server').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Gate').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Software').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc),
                             Catalog.query.get('SoftwareServerAssociation').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc),
                             Catalog.query.get('ActionTemplate').last_modified_at)

            resp = self.client1.get(url_for('root.healthcheck'))

        with self.app2.app_context():
            with self.app2.test_request_context('https://node1:5000/api/v1.0/catalog', headers=self.auth.header):
                verify_jwt_in_request()

                s = Server.query.filter_by(_me=False).one()
                update_catalog({s: Response(msg=resp.get_json(), code=resp.status_code)})
                db.session.commit()

        with self.app2.app_context():
            soft = Software.query.get('aaaaaaaa-1234-5678-1234-56781234aaa1')
            self.assertDictEqual(self.soft_json, soft.to_json())
            soft = ActionTemplate.query.get('aaaaaaaa-1234-5678-1234-56781234aaa2')
            self.assertDictEqual(self.at_json, soft.to_json())

            self.assertEqual(6, Catalog.query.count())
            self.assertEqual(defaults.INITIAL_DATEMARK, Catalog.query.get('User').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Software').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc),
                             Catalog.query.get('SoftwareServerAssociation').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc),
                             Catalog.query.get('ActionTemplate').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Server').last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc),
                             Catalog.query.get('Gate').last_modified_at)
