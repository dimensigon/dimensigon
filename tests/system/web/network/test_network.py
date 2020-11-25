import responses
from aioresponses import aioresponses

from dimensigon.domain.entities import Dimension, Server, Route, Gate
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db
from dimensigon.web.network import ping
from tests.base import TestDimensigonBase
from tests.helpers import generate_dimension_json_data, set_callbacks

now = get_now()


class TestPing(TestDimensigonBase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.dim = generate_dimension_json_data()

    def fill_database(self, node):
        db.create_all()
        d = Dimension.from_json(self.dim)
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
        super().setUp()
        self.app2 = create_app('test')
        self.app2.name = 'dimensigon2'
        self.client2 = self.app2.test_client()
        self.app3 = create_app('test')
        self.app3.name = 'dimensigon3'
        self.client3 = self.app3.test_client()

        # fill data
        self.fill_database('node1')

        with self.app2.app_context():
            self.fill_database('node2')

        with self.app3.app_context():
            self.fill_database('node3')

    @aioresponses()
    @responses.activate
    def test_ping(self, m):
        set_callbacks([('node1', self.client), ('node2', self.client2), ('node3', self.client3)], m)

        cost, time = ping(self.s1)
        self.assertEqual(0, cost)

        cost, time = ping(self.s2)
        self.assertEqual(0, cost)

        cost, time = ping(self.s3)
        self.assertEqual(1, cost)

        cost, time = ping(self.s4)
        self.assertEqual(None, cost)
