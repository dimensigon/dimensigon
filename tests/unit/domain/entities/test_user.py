from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm.domain.entities import User
from dm.network.auth import HTTPBearerAuth
from dm.web import create_app, db


class Test(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_verify_password(self):
        u = User(user='root', email=None, groups=['adm', 'dev'])
        u.set_password('test')
        self.assertIsNotNone(u._password)

        self.assertTrue(u.verify_password('test'))

    def test_to_from(self):
        u = User(user='root', email=None, groups=['adm', 'dev'])
        db.session.add(u)

        u_json = u.to_json(password=True)

        smashed = u.from_json(u_json)

        self.assertEqual(u, smashed)
        self.assertEqual(u.id, smashed.id)
        self.assertEqual(u.active, smashed.active)
        self.assertEqual(u.created_at, smashed.created_at)
        self.assertEqual(u.email, smashed.email)
        self.assertEqual(u.groups, smashed.groups)

        db.session.delete(u)

        smashed = u.from_json(u_json)

        self.assertEqual(u.id, smashed.id)
        self.assertEqual(u.active, smashed.active)
        self.assertEqual(u.created_at, smashed.created_at)
        self.assertEqual(u.email, smashed.email)
        self.assertEqual(u.groups, smashed.groups)

    def test_to_from_no_password(self):
        u = User(user='root', email=None, groups=['adm', 'dev'])
        db.session.add(u)

        u_json = u.to_json()

        smashed = User.from_json(u_json)

        self.assertEqual(u, smashed)
        self.assertEqual(u.id, smashed.id)
        self.assertEqual(u.active, smashed.active)
        self.assertEqual(u.created_at, smashed.created_at)
        self.assertEqual(u.email, smashed.email)
        self.assertEqual(u.groups, smashed.groups)

        db.session.delete(u)

        smashed = User.from_json(u_json)
        db.session.add(smashed)
        db.session.flush()

        self.assertEqual(u.id, smashed.id)
        self.assertEqual(u.active, smashed.active)
        self.assertEqual(u.created_at, smashed.created_at)
        self.assertEqual(u.email, smashed.email)
        self.assertEqual(u.groups, smashed.groups)


