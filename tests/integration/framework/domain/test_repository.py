from unittest import TestCase

import dm.framework.exceptions as exc
from dm.framework.data.dao import InMemoryDao
from dm.framework.domain import Entity, Id, Schema, fields, Repository
from dm.framework.interfaces.dao import IDao, Kwargs
from dm.framework.utils.dependency_injection import Container, Scopes


class Bike(Entity):
    # noinspection
    __id__ = Id(auto_fill=False)

    def __init__(self, frame_type, wheel_type, **kwargs):
        super().__init__(**kwargs)
        self.frame_type = frame_type
        self.wheel_type = wheel_type


class BikeSchema(Schema):
    __entity__ = Bike
    id = fields.Int(required=True)
    frame_type = fields.Str()
    wheel_type = fields.Str()


class TestConfig(TestCase):

    def setUp(self) -> None:
        self.data = {'frame_type': 'gravel', 'wheel_type': 'road'}
        self.schema = BikeSchema
        self.container = Container(default_scope=Scopes.SINGLETON)
        self.container.register_by_interface(
            IDao, InMemoryDao,
            qualifier=Bike,
            scope=Scopes.SINGLETON_NO_CONTAINER
        )
        self.dao = self.container.find_by_interface(IDao, qualifier=Bike)
        self.container.register_by_name(name='BikeSeq', constructor=self.dao._get_id)

        self.repo = Repository(self.container, self.schema)


class TestConstruction(TestConfig):

    def test_dao_injection_success(self):
        self.assertIs(self.repo.entity, Bike)
        self.assertIs(self.dao, self.repo.dao)

    def test_dao_injection_error(self):
        self.container._constructor_registry = {}
        self.assertIs(Bike, self.repo.entity)
        with self.assertRaises(exc.DefinitionNotFound) as error_info:
            assert self.repo.dao
        self.assertTupleEqual((IDao, Bike), error_info.exception.args)


class TestApi(TestConfig):

    def test_create(self):
        entity = self.repo.create(self.data)
        self.assertDictEqual({'frame_type': 'gravel', 'wheel_type': 'road', 'id': None},
                             self.repo.schema.deconstruct(entity))
        self.assertEqual(0, self.dao.all().count())

    def test_add(self):
        # noinspection PyArgumentList
        entity = Bike(**self.data)
        self.assertIsNone(entity.id)
        id_ = self.repo.add(entity)
        self.assertIsNotNone(entity.id)
        self.assertDictEqual(self.dao.get(id_), {'frame_type': 'gravel', 'wheel_type': 'road', 'id': 1})
        with self.assertRaises(exc.IdAlreadyExists):
            id_ = self.repo.add(entity)

    def test_create_and_add(self):
        entity = self.repo.create_and_add(self.data)
        self.assertIsNotNone(entity.id)
        self.assertDictEqual({'frame_type': 'gravel', 'wheel_type': 'road', 'id': 1}, self.dao.get(entity.id))

    def test_update(self):
        # noinspection PyArgumentList
        entity = self.repo.create_and_add(self.data)
        entity2 = self.repo.create_and_add(self.data)
        entity.frame_type = 'Ultralight Frame'
        self.assertNotEqual(entity.frame_type, self.repo.find(entity.id).frame_type)
        id_ = self.repo.update(entity)
        self.assertEqual(id_, entity.id)
        self.assertDictEqual(self.dao._register,
                             {entity.id: {'id': 1, 'frame_type': 'Ultralight Frame', 'wheel_type': 'road'},
                              entity2.id: {'id': 2, 'frame_type': 'gravel', 'wheel_type': 'road'}})

    def test_find_success(self):
        id_ = self.dao.insert(self.data)
        self.data.update(id=id_)
        entity = self.repo.find(id_)
        self.assertIsInstance(entity, Bike)
        self.assertDictEqual(self.data, self.schema().dump(entity))

    def test_find_error(self):
        id_ = 42
        with self.assertRaises(exc.NotFound) as error_info:
            self.repo.find(id_)
        self.assertTupleEqual((id_, Bike), error_info.exception.args)

    def test_contains_success(self):
        id_ = self.dao.insert(self.data)
        self.assertTrue(self.repo.contains(id_))

    def test_contains_failure(self):
        id_ = 42
        self.assertFalse(self.repo.contains(id_))

    def test_update_success(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        entity.frame_type = 'road'
        self.repo.update(entity)
        self.assertDictEqual({'id': 1, 'frame_type': 'road', 'wheel_type': 'road'}, self.dao.get(id_))

    def test_remove_success(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        self.assertTrue(self.dao.filter_by(id_=id_).exists())
        self.repo.remove(entity)
        self.assertFalse(self.dao.filter_by(id_=id_).exists())

    def test_remove_error_not_added(self):
        entity = self.repo.create(self.data)
        with self.assertRaises(exc.EntityNotYetAdded) as error_info:
            self.repo.remove(entity)
        self.assertTupleEqual(error_info.exception.args, (entity,))

    def test_remove_error_wrong_id(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        self.repo.remove(entity)
        with self.assertRaises(exc.NotFound) as error_info:
            self.repo.remove(entity)
        self.assertTupleEqual(error_info.exception.args, (id_, entity))


class BikeFieldNames(Entity):
    # noinspection
    __id__ = Id('frame_type', 'wheel_type')

    def __init__(self, frame_type, wheel_type, **kwargs):
        super().__init__(**kwargs)
        self.frame_type = frame_type
        self.wheel_type = wheel_type


class BikeSchemaFieldNames(Schema):
    __entity__ = BikeFieldNames
    id = fields.Int(required=True)
    frame_type = fields.Str()
    wheel_type = fields.Str()


class TestConfigFieldNames(TestCase):

    def setUp(self) -> None:
        self.data = {'frame_type': 'gravel', 'wheel_type': 'road'}
        self.schema = BikeSchemaFieldNames
        self.container = Container(default_scope=Scopes.SINGLETON)
        self.container.register_by_interface(
            IDao, InMemoryDao,
            qualifier=BikeFieldNames,
            scope=Scopes.SINGLETON_NO_CONTAINER
        )
        self.dao = self.container.find_by_interface(IDao, qualifier=BikeFieldNames)
        self.container.register_by_name(name='BikeSeq', constructor=self.dao._get_id)

        self.repo = Repository(self.container, self.schema)


class TestConstructionWithFieldNames(TestConfigFieldNames):

    def test_dao_injection_success(self):
        self.assertIs(self.repo.entity, BikeFieldNames)
        self.assertIs(self.dao, self.repo.dao)

    def test_dao_injection_error(self):
        self.container._constructor_registry = {}
        self.assertIs(BikeFieldNames, self.repo.entity)
        with self.assertRaises(exc.DefinitionNotFound) as error_info:
            assert self.repo.dao
        self.assertTupleEqual((IDao, BikeFieldNames), error_info.exception.args)


class TestApiWithFieldNames(TestConfig):

    def test_create(self):
        entity = self.repo.create(self.data)
        self.assertDictEqual({'frame_type': 'gravel', 'wheel_type': 'road', 'id': None},
                             self.repo.schema.deconstruct(entity))
        self.assertEqual(0, self.dao.all().count())

    def test_add(self):
        # noinspection PyArgumentList
        entity = Bike(**self.data)
        self.assertIsNone(entity.id)
        id_ = self.repo.add(entity)
        self.assertIsNotNone(entity.id)
        self.assertDictEqual(self.dao.get(id_), {'frame_type': 'gravel', 'wheel_type': 'road', 'id': 1})
        with self.assertRaises(exc.IdAlreadyExists):
            id_ = self.repo.add(entity)

    def test_create_and_add(self):
        entity = self.repo.create_and_add(self.data)
        self.assertIsNotNone(entity.id)
        self.assertDictEqual({'frame_type': 'gravel', 'wheel_type': 'road', 'id': 1}, self.dao.get(entity.id))

    def test_update(self):
        # noinspection PyArgumentList
        entity = self.repo.create_and_add(self.data)
        entity2 = self.repo.create_and_add(self.data)
        entity.frame_type = 'Ultralight Frame'
        self.assertNotEqual(entity.frame_type, self.repo.find(entity.id).frame_type)
        id_ = self.repo.update(entity)
        self.assertEqual(id_, entity.id)
        self.assertDictEqual({entity.id: {'id': 1, 'frame_type': 'Ultralight Frame', 'wheel_type': 'road'},
                              entity2.id: {'id': 2, 'frame_type': 'gravel', 'wheel_type': 'road'}},
                             self.dao._register
                             )

    def test_find_success(self):
        id_ = self.dao.insert(self.data)
        self.data.update(id=id_)
        entity = self.repo.find(id_)
        self.assertIsInstance(entity, Bike)
        self.assertDictEqual(self.data, self.schema().dump(entity))

    def test_find_error(self):
        id_ = 42
        with self.assertRaises(exc.NotFound) as error_info:
            self.repo.find(id_)
        self.assertTupleEqual((id_, Bike), error_info.exception.args)

    def test_contains_success(self):
        id_ = self.dao.insert(self.data)
        self.assertTrue(self.repo.contains(id_))

    def test_contains_failure(self):
        id_ = 42
        self.assertFalse(self.repo.contains(id_))

    def test_update_success(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        entity.frame_type = 'road'
        self.repo.update(entity)
        self.assertDictEqual({'frame_type': 'road', 'wheel_type': 'road', 'id': id_}, self.dao.get(id_))

    def test_remove_success(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        self.assertTrue(self.dao.filter_by(id_=id_).exists())
        self.repo.remove(entity)
        self.assertFalse(self.dao.filter_by(id_=id_).exists())

    def test_remove_error_not_added(self):
        entity = self.repo.create(self.data)
        with self.assertRaises(exc.EntityNotYetAdded) as error_info:
            self.repo.remove(entity)
        self.assertTupleEqual(error_info.exception.args, (entity,))

    def test_remove_error_wrong_id(self):
        id_ = self.dao.insert(self.data)
        entity = self.repo.find(id_)
        self.repo.remove(entity)
        with self.assertRaises(exc.NotFound) as error_info:
            self.repo.remove(entity)
        self.assertTupleEqual(error_info.exception.args, (id_, entity))
