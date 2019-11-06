import uuid
from unittest import TestCase, mock

from dm.framework.domain.entity import Entity, Id


class Service(Entity):
    __id__ = Id(auto_fill=True, factory=lambda: str(uuid.uuid1()))

    def __init__(self, name, servers, details, **kwargs):
        self.name = name
        self.servers = servers
        self.details = details
        super().__init__(**kwargs)


class Bike(Entity):
    def __init__(self, frame, wheel, **kwargs):
        super().__init__(**kwargs)
        self.wheel = wheel
        self.frame = frame


class Cycler(Entity):
    __id__ = Id('name')

    def __init__(self, name, age, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.age = age


class TestEntity(TestCase):
    def test_entity(self):
        with mock.patch('uuid.uuid1', side_effect=[uuid.UUID('12345678-1234-5678-1234-567812345678'),
                                                   uuid.UUID('12345678-1234-5678-1234-000000000000'),
                                                   uuid.UUID('12345678-1234-5678-1234-000000000001')]):
            data = {'name': 'mysql', 'servers': ('s1',), 'details': 'test details'}
            s1 = Service(**data)
            s2 = Service(**data)

            data = {'name': 'mysql', 'servers': ('s1',), 'details': 'test details', 'id': 1}

            s3 = Service(**data)

            self.assertEqual(hash(s1), hash('12345678-1234-5678-1234-567812345678'))
            self.assertEqual('12345678-1234-5678-1234-567812345678', s1.id)
            self.assertEqual('12345678-1234-5678-1234-000000000000', s2.id)
            self.assertNotEqual(s1, s2)
            self.assertEqual(1, s3.id)

            with mock.patch('random.randint', side_effect=[1]):
                b = Bike(frame='road', wheel='gravel')
                self.assertEqual(1, b.id)

    def test_entity_with_field_id(self):
        data = {'name': 'Joan', 'age': 24}
        c = Cycler(**data)

        self.assertEqual(('Joan', ), c.id)
