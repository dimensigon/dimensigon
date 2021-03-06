from unittest import TestCase

from dimensigon.domain.entities import Dimension, Server, Route, Gate
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db
from dimensigon.web.network import ping
from tests.base import virtual_network
from tests.helpers import generate_dimension_json_data, set_test_scoped_session, app_scope

now = get_now()


class TestPing(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def fill_database(self, node):
        db.create_all()
        d = Dimension.from_json(self.dim)
        d.current = True
        s1 = Server(id='00000000-0000-0000-0000-000000000001', name='node1', created_on=now, me=node == 'node1')
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=s1, port=5000, dns=s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2', created_on=now, me=node == 'node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3', created_on=now, me=node == 'node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4', created_on=now, me=node == 'node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        if node == 'node1':
            self.s1 = s1
            self.s2 = s2
            self.s3 = s3
            self.s4 = s4
            Route(s2, g12)
            Route(s3, s2, 1)
        elif node == 'node2':
            Route(s1, g11)
            Route(s3, g13)
        elif node == 'node3':
            Route(s1, s2, 1)
            Route(s2, g12)

        db.session.add_all([d, s1, s2, s3, s4])
        db.session.commit()

    def setUp(self) -> None:
        self.maxDiff = None
        set_test_scoped_session(db)
        self.app1 = create_app('test')
        self.app1.config['SERVER_NAME'] = 'node1'
        self.app_context = self.app1.app_context()
        self.app_context.push()
        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app3 = create_app('test')
        self.app3.config['SERVER_NAME'] = 'node3'

        self.fill_database('node1')

        with self.app2.app_context():
            self.fill_database('node2')

        with self.app3.app_context():
            self.fill_database('node3')

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_ping(self):
        with virtual_network(self.app1, self.app2, self.app3):
            cost, time = ping(self.s1)
            self.assertEqual(0, cost)

            cost, time = ping(self.s2)
            self.assertEqual(0, cost)

            cost, time = ping(self.s3)
            self.assertEqual(1, cost)

            cost, time = ping(self.s4)
            self.assertEqual(None, cost)
