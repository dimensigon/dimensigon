import copy
import uuid
from itertools import count
from unittest import TestCase, mock
from unittest.mock import create_autospec

from dm.framework.domain import fields, Entity, Id, Schema
from dm.framework.utils.dependency_injection import Container


class Seq:
    c = count(1)

    def next_(self):
        return next(self.c)


class User(Entity):
    __id__ = Id(factory=uuid.uuid1)

    def __init__(self, name, email, organization, load_only='load_only', dump_only=1, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.email = email
        self.organization = organization
        self.load_only = load_only
        self.dump_only = dump_only


class UserSchema(Schema):
    __entity__ = User
    id = fields.UUID(required=True, attribute='id')
    name = fields.Field(required=True)
    email = fields.Field()
    organization = fields.Field()
    country = fields.Field(default='Australia')
    missing = fields.Field(missing=1)
    load_only = fields.Field(load_only=True)
    dump_only = fields.Field(dump_only=True)


class Blog(Entity):
    __id__ = Id('title')

    def __init__(self, title, author, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.author = author


class BlogNestedSchema(Schema):
    __entity__ = Blog
    title = fields.Field(required=True)
    author = fields.Nested(UserSchema, only=('id',))


class BlogPluckSchema(Schema):
    __entity__ = Blog
    title = fields.Field(required=True)
    author = fields.PluckEntity(UserSchema, field_name='id')


class Food(Entity):
    __id__ = Id('name')

    def __init__(self, name, calories, sugar, fiber, **kwargs):
        super().__init__(**kwargs)
        self.calories = calories
        self.name = name
        self.sugar = sugar
        self.fiber = fiber


class Category(Entity):
    __id__ = Id('category')

    def __init__(self, category, food, **kwargs):
        super().__init__(**kwargs)
        self.category = category
        self.food = food


class FoodSchema(Schema):
    __entity__ = Food
    name = fields.Str()
    calories = fields.Int()
    sugar = fields.Float()
    fiber = fields.Float()


class CategoryNestedSchema(Schema):
    __entity__ = Category
    category = fields.Str(required=True)
    food = fields.Nested(FoodSchema, many=True, only=('name',))


class CategoryPluckSchema(Schema):
    __entity__ = Category
    category = fields.Str()
    food = fields.PluckEntity(FoodSchema, many=True, field_name='name')


class Action(Entity):
    __id__ = Id(factory=uuid.uuid1)

    def __init__(self, name, code, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.code = code


class ActionSchema(Schema):
    __entity__ = Action
    id = fields.UUID(required=True)
    name = fields.Str(required=True)
    code = fields.Str(required=True)


class Step(Entity):
    __id__ = Id('name')

    def __init__(self, name, undo, action, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.undo = undo
        self.action = action


class StepSchema(Schema):
    __entity__ = Step
    name = fields.Str(required=True)
    undo = fields.Bool()
    action = fields.PluckEntity(ActionSchema, field_name='id')


class Orchestration(Entity):
    __id__ = Id('name')

    def __init__(self, name, steps, dependencies, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.steps = steps
        self.dependencies = dependencies


class OrchestrationSchema(Schema):
    __entity__ = Orchestration
    name = fields.Str(required=True)
    steps = fields.PluckEntity(StepSchema, field_name='name', many=True)
    dependencies = fields.MappingEntity(keys=fields.Str(),
                                        values=fields.PluckEntity(StepSchema, field_name='name', as_is=True, many=True))


class Artist(Entity):
    __id__ = Id('name')

    def __init__(self, name, email, friends, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.email = email
        self.friends = friends


class ArtistSchema(Schema):
    __entity__ = Artist

    name = fields.String()
    email = fields.Email()
    friends = fields.PluckEntity("self", field_name="name", many=True)


def mock_container(data):
    def dao_get(id_):
        return copy.deepcopy(data.get(id_))

    mocked_container = create_autospec(Container)
    # mocked_container = mock.MagicMock()
    mock_dao = mock.MagicMock()

    mocked_container.find_by_interface.return_value = mock_dao

    mock_dao.get.side_effect = dao_get
    return mocked_container


class TestSchemaWithUUIDId(TestCase):

    def setUp(self) -> None:
        self.schema = UserSchema()

    def test_deconstruct(self):
        user = User('Joan', 'joan@domain.com', 'Dimensigon', id=uuid.UUID('12345678-1234-5678-1234-567812345678'))

        user_dto = self.schema.deconstruct(user)

        self.assertDictEqual(user_dto,
                             {'name': 'Joan', 'email': 'joan@domain.com', 'dump_only': 1, 'country': 'Australia',
                              'organization': 'Dimensigon', 'id': '12345678-1234-5678-1234-567812345678'})

    def test_construct(self):
        user_dto = {'id': '12345678-1234-5678-1234-567812345678', 'name': 'Joan', 'email': 'joan@domain.com',
                    'load_only': 1, 'organization': 'Dimensigon'}

        user = self.schema.construct(user_dto)

        self.assertEqual(user.id, uuid.UUID('12345678-1234-5678-1234-567812345678'))
        self.assertEqual(user.name, 'Joan')
        self.assertEqual(user.email, 'joan@domain.com')
        self.assertEqual(user.load_only, 1)
        self.assertEqual(user.dump_only, 1)
        self.assertEqual(user.name, 'Joan')


class TestSchemaWithFieldId(TestCase):

    def setUp(self) -> None:
        self.schema = FoodSchema()
        self.data = {'name': 'apple', 'calories': 52, 'sugar': 10.4, 'fiber': 2.4}

    def test_deconstruct(self):
        food = Food(**self.data)

        food_dto = self.schema.deconstruct(food)

        self.assertDictEqual(food_dto, self.data)

    def test_construct(self):
        food_dto = self.data

        food = self.schema.construct(food_dto)

        self.assertIsInstance(food, Food)
        self.assertEqual(food.id, ('apple',))
        self.assertDictEqual(food.__dict__, self.data)


class TestSchemaWithNestedUUIDId(TestCase):

    def setUp(self) -> None:
        self.uuid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        self.data = {
            str(self.uuid): {'id': str(self.uuid), 'name': 'Joan',
                             'email': 'joan@domain.com', 'organization': 'Dimensigon'},
            ('IoT Automation',): {'title': 'IoT Automation', 'author': {'id': str(self.uuid)}}}

        self.user = User(id=self.uuid, name='Joan', email='joan@domain.com', organization='Dimensigon')
        self.blog = Blog(title='IoT Automation', author=self.user)

        self.mocked_container = mock_container(self.data)
        BlogNestedSchema.set_container(self.mocked_container)
        UserSchema.set_container(self.mocked_container)
        self.blog_schema = BlogNestedSchema()

    def test_deconstruct(self):
        blog_dto = self.blog_schema.deconstruct(self.blog)

        self.assertDictEqual(blog_dto, self.data[('IoT Automation',)])

    def test_construct(self):
        blog_dto = self.data[('IoT Automation',)]
        blog = self.blog_schema.construct(blog_dto)

        self.assertIsInstance(blog.author, User)
        self.assertEqual(blog.author, self.user)
        self.assertDictEqual(blog.author.__dict__, self.user.__dict__)


class TestSchemaWithNestedField(TestCase):

    def setUp(self) -> None:
        self.data = {('apple',): {'name': 'apple', 'calories': 52, 'sugar': 10.4, 'fiber': 2.4},
                     ('banana',): {'name': 'banana', 'calories': 105, 'sugar': 14.4, 'fiber': 3.1},
                     ('fruit',): {'category': 'fruit', 'food': [{'name': 'apple'}, {'name': 'banana'}]}}

        self.apple = Food(**self.data[('apple',)])
        self.banana = Food(**self.data[('banana',)])

        self.fruit = Category('fruit', [self.apple, self.banana])

        self.mocked_container = mock_container(self.data)
        FoodSchema.set_container(self.mocked_container)
        CategoryNestedSchema.set_container(self.mocked_container)
        self.food_schema = FoodSchema()
        self.category_schema = CategoryNestedSchema()

    def test_deconstruct(self):
        fruit_dto = self.category_schema.deconstruct(self.fruit)

        self.assertDictEqual(fruit_dto, self.data[('fruit',)])

    def test_construct(self):
        fruit = self.category_schema.construct(
            self.data[('fruit',)])

        self.assertIsInstance(self.fruit.food[0], Food)
        self.assertListEqual(self.fruit.food, fruit.food)
        self.assertDictEqual(self.fruit.food[0].__dict__, fruit.food[0].__dict__)


class TestSchemaWithPluckUUIDId(TestCase):

    def setUp(self) -> None:
        self.uuid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        self.data = {str(self.uuid): {'id': str(self.uuid), 'name': 'Joan', 'email': 'joan@domain.com',
                                      'organization': 'Dimensigon'},
                     ('IoT Automation',): {'title': 'IoT Automation', 'author': str(self.uuid)}}

        self.user = User(id=self.uuid, name='Joan', email='joan@domain.com', organization='Dimensigon')
        self.blog = Blog(title='IoT Automation', author=self.user)

        self.mocked_container = mock_container(self.data)
        BlogPluckSchema.set_container(self.mocked_container)
        UserSchema.set_container(self.mocked_container)
        self.blog_schema = BlogPluckSchema()
        self.user_schema = UserSchema()

    def test_deconstruct(self):
        blog_dto = self.blog_schema.deconstruct(self.blog)

        self.assertDictEqual(blog_dto, self.data[('IoT Automation',)])

    def test_construct(self):
        blog_dto = self.data[('IoT Automation',)]
        blog = self.blog_schema.construct(blog_dto)

        self.assertIsInstance(blog.author, User)
        self.assertEqual(blog.author, self.user)
        self.assertDictEqual(blog.author.__dict__, self.user.__dict__)


class TestSchemaWithPluckFields(TestCase):

    def setUp(self) -> None:
        self.data = {('apple',): {'name': 'apple', 'calories': 52, 'sugar': 10.4, 'fiber': 2.4},
                     ('banana',): {'name': 'banana', 'calories': 105, 'sugar': 14.4, 'fiber': 3.1},
                     ('fruit',): {'category': 'fruit', 'food': "['apple', 'banana']"}}

        self.apple = Food(**self.data[('apple',)])
        self.banana = Food(**self.data[('banana',)])

        self.fruit = Category('fruit', [self.apple, self.banana])

        self.mocked_container = mock_container(self.data)
        FoodSchema.set_container(self.mocked_container)
        CategoryPluckSchema.set_container(self.mocked_container)
        self.food_schema = FoodSchema()
        self.category_schema = CategoryPluckSchema()

    def test_deconstruct(self):
        fruit_dto = self.category_schema.deconstruct(self.fruit)

        self.assertDictEqual({'category': 'fruit', 'food': "['apple', 'banana']"}, fruit_dto)

    def test_construct(self):
        fruit = self.category_schema.construct(self.data[('fruit',)])

        self.assertIsInstance(self.fruit.food[0], Food)
        self.assertListEqual(self.fruit.food, fruit.food)
        self.assertDictEqual(self.fruit.food[0].__dict__, fruit.food[0].__dict__)


class TestSchemaWithMapping(TestCase):

    def setUp(self) -> None:
        self.data = {'aaaa1111-2222-3333-4444-55556666aaa1': {'id': 'aaaa1111-2222-3333-4444-55556666aaa1',
                                                              'name': 'action1',
                                                              'code': 'cmd1'},
                     'aaaa1111-2222-3333-4444-55556666aaa2': {'id': 'aaaa1111-2222-3333-4444-55556666aaa2',
                                                              'name': 'action2',
                                                              'code': 'cmd2'},
                     ('step1',): {'name': 'step1', 'undo': False, 'action': 'aaaa1111-2222-3333-4444-55556666aaa1'},
                     ('step2',): {'name': 'step2', 'undo': True, 'action': 'aaaa1111-2222-3333-4444-55556666aaa2'},
                     ('orch',): {'name': 'orch', 'steps': "['step1', 'step2']", 'dependencies': "{'step1': ['step2']}"}}

        Action.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('aaaa1111-2222-3333-4444-55556666aaa1'),
                                                            uuid.UUID('aaaa1111-2222-3333-4444-55556666aaa2')])
        self.action1 = Action(name='action1', code='cmd1')
        self.action2 = Action(name='action2', code='cmd2')
        self.step1 = Step(name='step1', undo=False, action=self.action1)
        self.step2 = Step(name='step2', undo=True, action=self.action2)
        self.orch = Orchestration(name='orch', steps=[self.step1, self.step2], dependencies={'step1': [self.step2]})

        self.mocked_container = mock_container(self.data)
        ActionSchema.set_container(self.mocked_container)
        StepSchema.set_container(self.mocked_container)
        OrchestrationSchema.set_container(self.mocked_container)
        self.action_schema = ActionSchema()
        self.step_schema = StepSchema()
        self.orch_schema = OrchestrationSchema()

    def test_deconstruct(self):
        orch_dto = self.orch_schema.deconstruct(self.orch)

        self.assertDictEqual(orch_dto, self.data[('orch',)])

    def test_construct(self):
        orch_dto = self.data[('orch',)]
        orch = self.orch_schema.construct(orch_dto)

        self.assertDictEqual(orch.__dict__, self.orch.__dict__)
        self.assertIsInstance(orch.steps[0].action, Action)
        self.assertEqual(orch.steps[0].action, self.orch.steps[0].action)
        self.assertDictEqual(orch.steps[0].action.__dict__, self.orch.steps[0].action.__dict__)


class TestSchemaWithPluckSelf(TestCase):

    def setUp(self) -> None:
        self.data = {('Joan',): {'name': 'Joan', 'email': 'joan@domain.com',
                                 'friends': []},
                     ('Joe',): {'name': 'Joe', 'email': 'joe@domain.com',
                                'friends': "['Joan', 'Josep']"},
                     ('Josep',): {'name': 'Josep', 'email': 'josep@domain.com',
                                  'friends': []}
                     }

        self.joan = Artist(name='Joan', email='joan@domain.com', friends=[])
        self.josep = Artist(name='Josep', email='josep@domain.com', friends=[])
        self.entity = Artist(name='Joe', email='joe@domain.com', friends=[self.joan, self.josep])

        self.mocked_container = mock_container(self.data)
        ArtistSchema.set_container(self.mocked_container)
        self.schema = ArtistSchema()

    def test_deconstruct(self):
        dto = self.schema.deconstruct(self.entity)

        self.assertDictEqual(dto, self.data[('Joe',)])

    def test_construct(self):
        dto = self.data[('Joe',)]
        entity = self.schema.construct(dto)

        self.assertDictEqual(entity.__dict__, self.entity.__dict__)
        self.assertIsInstance(entity.friends[0], Artist)
        self.assertListEqual(entity.friends, self.entity.friends)
        self.assertDictEqual(entity.friends[0].__dict__, self.entity.friends[0].__dict__)
