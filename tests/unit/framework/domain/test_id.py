import uuid
from unittest import TestCase, mock

from dm.framework.domain.entity import Id


class Service:
    id = Id(auto_fill=True, factory=lambda: str(uuid.uuid1()))

    def __init__(self, name, servers, details, id_=None):
        self.name = name
        self.servers = servers
        self.details = details
        if id_:
            self.id = id_


class Server:
    id = Id('name', 'port')

    def __init__(self, name, ip, port):
        self.name = name
        self.ip = ip
        self.port = port


class Interpreter:
    id = Id(auto_fill=False)

    def __init__(self, name, people, id_=None):
        self.name = name
        self.people = people
        if id_:
            self.id = id_


class TestId(TestCase):
    uuid_mock = mock.MagicMock(side_effect=[uuid.UUID('12345678-1234-5678-1234-567812345678'),
                                            uuid.UUID('12345678-1234-5678-1234-000000000000'),
                                            uuid.UUID('12345678-1234-5678-1234-000000000001')])

    def test_id_factory(self):
        with mock.patch('uuid.uuid1', side_effect=[uuid.UUID('12345678-1234-5678-1234-567812345678'),
                                                   uuid.UUID('12345678-1234-5678-1234-000000000000'),
                                                   uuid.UUID('12345678-1234-5678-1234-000000000001')]):
            data = {'name': 'mysql', 'servers': ('s1', 's2'), 'details': 'test details'}
            s1 = Service(**data)
            s2 = Service(**data)

            self.assertEqual('12345678-1234-5678-1234-567812345678', s1.id)
            self.assertEqual('12345678-1234-5678-1234-000000000000', s2.id)

            with self.assertRaises(AttributeError):
                s1.id = 2

            s3 = Service(**data)
            s3.id = 2
            self.assertEqual(2, s3.id)

            with self.assertRaises(AttributeError):
                s3.id = 4

            data.update({'id_': 1})
            s3 = Service(**data)
            self.assertEqual(1, s3.id)
            with self.assertRaises(AttributeError):
                s3.id = 2

    def test_id_field_names(self):
        data = {'name': 'server1', 'ip': '127.0.0.1', 'port': 80}
        s1 = Server(**data)
        self.assertEqual(('server1', 80), s1.id)

        with self.assertRaises(AttributeError):
            s1.id = 2

    def test_id_auto_fill(self):
        data = {'name': 'Eivibonny', 'people': 4}
        i = Interpreter(**data)
        self.assertIsNone(i.id)
        i.id = 1
        self.assertEqual(1, i.id)

        with self.assertRaises(AttributeError):
            i.id = 2


