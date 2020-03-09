import datetime
import uuid
from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm.domain.entities import ActionTemplate, ActionType
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('test')}"}

        db.create_all()
        set_initial()
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        at = ActionTemplate(id=uuid.uuid4(), name='ActionTest2', version=1, action_type=ActionType.ORCHESTRATION,
                            code='test code',
                            last_modified_at=datetime.datetime.now())

        db.session.add(at)

        at_json = at.to_json()

        at_json['name'] = "ChangedAction"

        smashed = ActionTemplate.from_json(at_json)

        self.assertEqual(at.id, smashed.id)
        self.assertIsNotNone(smashed.id)
        self.assertEqual("ChangedAction", smashed.name)
        self.assertIsNotNone(smashed.name)
        self.assertEqual(at.version, smashed.version)
        self.assertIsNotNone(smashed.version)
        self.assertEqual(at.action_type, smashed.action_type)
        self.assertIsNotNone(smashed.action_type)
        self.assertEqual(at.code, smashed.code)
        self.assertIsNotNone(smashed.code)
        self.assertEqual(at.last_modified_at, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)

        db.session.commit()

        del at
        del smashed

        at = ActionTemplate.query.get(at_json['id'])
        self.assertEqual("ChangedAction", at.name)

    def test_to_from_json_no_app(self):
        self.app_context.pop()
        at = ActionTemplate(id=uuid.uuid4(), name='ActionTest2', version=1, action_type=ActionType.ORCHESTRATION,
                            code='test code',
                            last_modified_at=datetime.datetime.now())

        smashed = ActionTemplate.from_json(at.to_json())

        self.assertEqual(at.id, smashed.id)
        self.assertIsNotNone(smashed.id)
        self.assertEqual(at.name, smashed.name)
        self.assertIsNotNone(smashed.name)
        self.assertEqual(at.version, smashed.version)
        self.assertIsNotNone(smashed.version)
        self.assertEqual(at.action_type, smashed.action_type)
        self.assertIsNotNone(smashed.action_type)
        self.assertEqual(at.code, smashed.code)
        self.assertIsNotNone(smashed.code)
        self.assertEqual(at.last_modified_at, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)
        self.app_context.push()

    def test_to_from_json_no_id(self):
        at = ActionTemplate(name='ActionTest2', version=1, action_type=ActionType.ORCHESTRATION,
                            code='test code',
                            last_modified_at=datetime.datetime.now())

        smashed = ActionTemplate.from_json(at.to_json())

        self.assertEqual(at.id, smashed.id)

        self.app_context.push()
