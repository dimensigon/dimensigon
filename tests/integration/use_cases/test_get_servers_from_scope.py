import datetime as dt
import random
from unittest import TestCase, mock

from dimensigon import defaults
from dimensigon.domain.entities import Server, Route, Scope
from dimensigon.web import db
from dimensigon.web.helpers import get_servers_from_scope
from tests.base import FlaskAppMixin

old_age = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
now = dt.datetime(2019, 5, 1, tzinfo=dt.timezone.utc)


class Test(FlaskAppMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.app.config['SERVER_NAME'] = 'me'

    @mock.patch('dimensigon.web.helpers.current_app')
    @mock.patch('dimensigon.web.helpers.get_now')
    def test_get_servers_from_scope_one_server(self, mock_get_now, mock_app):
        mock_get_now.return_value = now
        s0 = Server(id='00000000-0000-0000-0000-000000000000', name='node0', port=5000, me=True, created_on=old_age)
        db.session.add(s0)
        mock_app.dm.cluster_manager.get_alive.return_value = [s0.id]

        quorum = get_servers_from_scope(scope=Scope.CATALOG)
        self.assertEqual([s0], quorum)

        s0.created_on = now
        db.session.flush()

        quorum = get_servers_from_scope(scope=Scope.CATALOG)
        self.assertEqual([s0], quorum)

        mock_app.dm.cluster_manager.get_alive.return_value = []

        quorum = get_servers_from_scope(scope=Scope.CATALOG)
        self.assertEqual([s0], quorum)

        s0.l_ignore_on_lock = True
        db.session.flush()

        quorum = get_servers_from_scope(scope=Scope.CATALOG)
        self.assertEqual([], quorum)

    @mock.patch('dimensigon.web.helpers.defaults.MIN_SERVERS_QUORUM', 2)
    @mock.patch('dimensigon.web.helpers.current_app')
    @mock.patch('dimensigon.web.helpers.get_now')
    def test_get_servers_from_scope_young_server(self, mock_get_now, mock_app):
        mock_get_now.return_value = now
        s0 = Server(id='00000000-0000-0000-0000-000000000000', name='node0', port=5000, me=True, created_on=now)
        s1 = Server(id='00000000-0000-0000-0000-000000000001', name='node1', port=5000, created_on=now)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2', port=5000, created_on=now)
        db.session.add_all([s0, s1, s2])
        mock_app.dm.cluster_manager.get_alive.return_value = [s1.id, s2.id]

        quorum = get_servers_from_scope(scope=Scope.CATALOG)
        self.assertEqual([s0, s1], quorum)

    @mock.patch('dimensigon.web.helpers.defaults.MIN_SERVERS_QUORUM', 5)
    @mock.patch('dimensigon.web.helpers.current_app')
    @mock.patch('dimensigon.domain.entities.get_now')
    def test_get_servers_from_scope_more_than_min_quorum(self, mock_get_now, mock_app):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        Server.set_initial()
        servers = []
        for i in range(0, 7):

            s = Server(f'node{i}', port=5000, created_on=old_age)

            if i == 0:
                r = Route(s, cost=0)
            else:
                r = Route(s, random.choice(servers), cost=i)

            db.session.add_all([s, r])

            servers.append(s)

        mock_get_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        mock_app.dm.cluster_manager.get_alive.return_value = [s.id for s in servers]
        s62 = Server(f'node72', port=5000)
        Route(s62, random.choice(servers), cost=6)
        db.session.add(s62)

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(8, len(quorum))
        self.assertNotIn(s62, quorum)
        self.assertIn(s, quorum)
        self.assertIn(Server.get_current(), quorum)

    @mock.patch('dimensigon.web.helpers.defaults.MIN_SERVERS_QUORUM', 5)
    @mock.patch('dimensigon.web.helpers.current_app')
    @mock.patch('dimensigon.domain.entities.get_now')
    def test_get_servers_from_scope_less_than_min_quorum(self, mock_get_now, mock_app):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        me = Server(id='00000000-0000-0000-0000-000000000000', name='node0', port=5000, me=True, created_on=now)
        db.session.add(me)
        servers = []
        for i in range(1, 4):
            s = Server(f'node{i}', port=5000, created_on=old_age)
            r = Route(s, cost=0)

            db.session.add_all([s, r])

            servers.append(s)

        mock_app.dm.cluster_manager.get_alive.return_value = [s.id for s in servers]

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(4, len(quorum))
        self.assertIn(Server.get_current(), quorum)

    @mock.patch('dimensigon.web.helpers.defaults.MIN_SERVERS_QUORUM', 5)
    @mock.patch('dimensigon.web.helpers.current_app')
    @mock.patch('dimensigon.domain.entities.get_now')
    def test_get_servers_from_scope_more_than_min_quorum_no_cost(self, mock_get_now, mock_app):
        mock_get_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        Server.set_initial()
        servers = []
        for i in range(0, 7):

            s = Server(f'node{i}', port=5000, created_on=old_age)

            if i == 0:
                r = Route(s, cost=0)
            else:
                r = Route(s, cost=0)

            db.session.add_all([s, r])

            servers.append(s)
        mock_app.dm.cluster_manager.get_alive.return_value = [s.id for s in servers]

        mock_get_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        s62 = Server(f'node72', port=5000)
        Route(s62, proxy_server_or_gate=random.choice(servers), cost=6)
        db.session.add(s62)

        quorum = get_servers_from_scope(scope=Scope.CATALOG)

        self.assertEqual(defaults.MIN_SERVERS_QUORUM + 1, len(quorum))
        self.assertIn(Server.get_current(), quorum)
