from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Orchestration, ActionTemplate, ActionType
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth
from tests.helpers import TestCaseLockBypass


class Test(TestCaseLockBypass):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        set_initial()
        self.at = ActionTemplate(name='action_name', version=1, action_type=ActionType.NATIVE, code='')
        self.o = Orchestration(name='name', version=1)
        self.s1 = self.o.add_step(undo=False, action_template=self.at)
        self.s2 = self.o.add_step(undo=False, action_template=self.at, children=[self.s1])
        self.s3 = self.o.add_step(undo=False, action_template=self.at, children=[self.s2])
        db.session.add_all([self.at, self.o])

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.steprelationshipchildrenresource', step_id=str(self.s1.id)),
                               headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(child_step_ids=[]), resp.get_json())

        resp = self.client.get(url_for('api_1_0.steprelationshipchildrenresource', step_id=str(self.s2.id)),
                               headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(child_step_ids=[str(self.s1.id)]), resp.get_json())

    def test_patch(self):
        resp = self.client.patch(url_for('api_1_0.steprelationshipchildrenresource', step_id=str(self.s3.id)),
                                 json={'child_step_ids': [str(self.s1.id)]},
                                 headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(child_step_ids=[str(self.s1.id)]), resp.get_json())
        self.assertListEqual([self.s1], self.s3.children)

    def test_post(self):
        resp = self.client.post(url_for('api_1_0.steprelationshipchildrenresource', step_id=str(self.s3.id)),
                                json={'child_step_ids': [str(self.s1.id)]},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        expected = [str(self.s2.id), str(self.s1.id)]
        expected.sort()
        actual = resp.get_json()['child_step_ids']
        actual.sort()
        self.assertListEqual(expected, actual)
        self.assertIn(self.s1, self.s3.children)
        self.assertIn(self.s2, self.s3.children)

    def test_delete(self):
        resp = self.client.delete(url_for('api_1_0.steprelationshipchildrenresource', step_id=str(self.s3.id)),
                                  json={'child_step_ids': [str(self.s2.id)]},
                                  headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(child_step_ids=[]), resp.get_json())
        self.assertEqual(0, len(self.s3.children))
