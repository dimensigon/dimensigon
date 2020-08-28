from unittest import TestCase, mock

from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import User
from dimensigon.domain.entities.base import SoftDeleteMixin, DistributedEntityMixin
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class EntityWithSoftDelete(db.Model, SoftDeleteMixin):
    __tablename__ = 'E'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    _old_name = db.Column(db.Text)


class DistEntityWithSoftDelete(db.Model, DistributedEntityMixin, SoftDeleteMixin):
    __tablename__ = 'DE'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    _old_name = db.Column(db.Text)


    def to_json(self):
        data = super().to_json()
        data.update(id=self.id, name=self.name)
        return data


class Test(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_entity_and_delete(self):
        e = EntityWithSoftDelete(id=1, name='first')

        self.assertFalse(e.deleted)

        db.session.add(e)
        db.session.commit()

        e.delete()

        self.assertTrue(e.deleted)

        self.assertEqual('first', e._old_name)
        self.assertNotEqual('first', e.name)

        db.session.commit()

        entities = EntityWithSoftDelete.query.all()

        self.assertEqual(0, len(entities))

    @mock.patch('dimensigon.domain.entities.base.random.choices')
    def test_create_distributed_entity_and_delete(self, mock_choices):

        mock_choices.return_value = list('abc')
        e = DistEntityWithSoftDelete(id=1, name='first', last_modified_at=defaults.INITIAL_DATEMARK)

        self.assertFalse(e.deleted)

        db.session.add(e)
        db.session.commit()

        dto = e.to_json()
        dto.pop('last_modified_at')
        self.assertDictEqual({'id': 1, 'name': 'first', 'deleted': False, '_old_name': None}, dto)

        e.delete()

        self.assertTrue(e.deleted)

        dto = e.to_json()
        dto.pop('last_modified_at')
        self.assertDictEqual({'id': 1, 'name': 'abc', 'deleted': True, '_old_name': 'first'}, dto)

        db.session.commit()

        dto = e.to_json(no_delete=True)
        dto.pop('last_modified_at')
        self.assertDictEqual({'id': 1, 'name': 'abc'}, dto)

        entities = EntityWithSoftDelete.query.all()

        self.assertEqual(0, len(entities))


