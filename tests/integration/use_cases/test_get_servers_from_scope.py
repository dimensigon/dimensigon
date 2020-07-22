import datetime as dt
import random
from unittest import TestCase, mock

from flask_jwt_extended import create_access_token

from dm import defaults
from dm.domain.entities import User, Server, Route, Scope
from dm.domain.entities.bootstrap import set_initial
from dm.network.auth import HTTPBearerAuth
from dm.use_cases.helpers import get_servers_from_scope
from dm.web import create_app, db


class Test(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial(user=True)
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dm.domain.entities.get_now')
    def test_get_servers_from_scope_more_than_min_quorum(self, mock_get_now):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)

        servers = []
        for i in range(0, 7):

            s = Server(f'node{i}', port=5000)

            if i == 0:
                r = Route(s, cost=0)
            else:
                r = Route(s, proxy_server=random.choice(servers), cost=i)

            db.session.add_all([s, r])

            servers.append(s)

        mock_get_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        s62 = Server(f'node72', port=5000)
        Route(s62, proxy_server=random.choice(servers), cost=6)
        db.session.add(s62)

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(8, len(quorum))
        self.assertNotIn(s62, quorum)
        self.assertIn(s, quorum)
        self.assertIn(Server.get_current(), quorum)

    @mock.patch('dm.domain.entities.get_now')
    def test_get_servers_from_scope_less_than_min_quorum(self, mock_get_now):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)

        servers = []
        for i in range(1, 4):
            s = Server(f'node{i}', port=5000)
            r = Route(s, cost=0)

            db.session.add_all([s, r])

            servers.append(s)

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(4, len(quorum))
        self.assertIn(Server.get_current(), quorum)

    @mock.patch('dm.domain.entities.get_now')
    def test_get_servers_from_scope_more_than_min_quorum_no_cost(self, mock_get_now):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)

        servers = []
        for i in range(0, 7):

            s = Server(f'node{i}', port=5000)

            if i == 0:
                r = Route(s, cost=0)
            else:
                r = Route(s, cost=0)

            db.session.add_all([s, r])

            servers.append(s)

        mock_get_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        s62 = Server(f'node72', port=5000)
        Route(s62, proxy_server=random.choice(servers), cost=6)
        db.session.add(s62)

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(defaults.MIN_SERVERS_QUORUM+1, len(quorum))
        self.assertIn(Server.get_current(), quorum)
