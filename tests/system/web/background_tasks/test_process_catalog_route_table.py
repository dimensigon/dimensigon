import datetime as dt
from unittest import TestCase
from unittest.mock import patch

import responses
from aioresponses import aioresponses
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Locker, Catalog
from dimensigon.domain.entities import Server, Route, Dimension, User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import create_app, db
from dimensigon.web.background_tasks import process_catalog_route_table
from tests.helpers import set_callbacks


class TestProcessCatalogRouteTable(TestCase):

    @patch('dimensigon.domain.entities.get_now')
    def setUp(self, mock_now):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SECURIZER'] = True
        mock_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        with self.app.app_context():
            self.dim = generate_dimension('test')
            self.dim.current = True
            self.json_dim = self.dim.to_json()
            self.client = self.app.test_client()

            db.create_all()
            Locker.set_initial()
            User.set_initial()

            self.auth = HTTPBearerAuth(create_access_token(User.get_by_name('root').id))

            server = Server('node1', dns_or_ip='127.0.0.1', port=8000, me=True)
            for g in server.gates:
                g.last_modified_at = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
            db.session.add_all([server, self.dim])
            db.session.commit()

            # dump data
            self.json_node1 = server.to_json(add_gates=True)
            self.json_users = [u.to_json() for u in User.query.all()]

        self.app2 = create_app('test')
        self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()
        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        with self.app2.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()

            me = Server('node2', port=8000, me=True, granules='granule',
                        last_modified_at=dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc))
            for g in me.gates:
                g.last_modified_at = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
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

        mock_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        with self.app.app_context():
            node2 = Server.from_json(self.json_node2)
            node2.last_modified_at = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
            Route(node2, cost=0)
            db.session.add(node2)
            db.session.commit()

    def tearDown(self) -> None:
        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @responses.activate
    @aioresponses()
    @patch('dimensigon.web.background_tasks.update_route_table_cost', return_value=True)
    @patch('dimensigon.web.background_tasks.upgrade_version', return_value=False)
    def test_catalog(self, m, mock_version, mock_routing):
        # test all system from process_catalog_route_table to lock server and upgrade catalog
        set_callbacks([("(127.0.0.1|node1)", self.app.test_client()),
                       ("node2", self.app2.test_client())], m=m)

        with self.app.app_context():
            datemark = Catalog.max_catalog()
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), datemark)

        process_catalog_route_table(self.app)

        with self.app.app_context():
            datemark = Catalog.max_catalog()
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), datemark.astimezone(dt.timezone.utc))
