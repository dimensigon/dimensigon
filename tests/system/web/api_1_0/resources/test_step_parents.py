from flask import url_for

from dimensigon.domain.entities import Orchestration, ActionTemplate, ActionType
from dimensigon.web import db
from tests.base import TestResourceBase


class Test(TestResourceBase):

    def fill_database(self):
        self.at = ActionTemplate(name='action_name', version=1, action_type=ActionType.SHELL, code='')
        self.o = Orchestration(name='name', version=1)
        self.st1 = self.o.add_step(undo=False, action_template=self.at)
        self.st2 = self.o.add_step(undo=False, action_template=self.at, parents=[self.st1])
        self.st3 = self.o.add_step(undo=False, action_template=self.at, parents=[self.st2])
        db.session.add_all([self.at, self.o])

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.steprelationshipparents', step_id=str(self.st1.id)),
                               headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(parent_step_ids=[]), resp.get_json())

        resp = self.client.get(url_for('api_1_0.steprelationshipparents', step_id=str(self.st2.id)),
                               headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(parent_step_ids=[str(self.st1.id)]), resp.get_json())

    def test_patch(self):
        resp = self.client.patch(url_for('api_1_0.steprelationshipparents', step_id=str(self.st3.id)),
                                 json={'parent_step_ids': [str(self.st1.id)]},
                                 headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(parent_step_ids=[str(self.st1.id)]), resp.get_json())
        self.assertListEqual([self.st1], self.st3.parents)

    def test_post(self):
        resp = self.client.post(url_for('api_1_0.steprelationshipparents', step_id=str(self.st3.id)),
                                json={'parent_step_ids': [str(self.st1.id)]},
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        expected = [str(self.st2.id), str(self.st1.id)]
        expected.sort()
        actual = resp.get_json()['parent_step_ids']
        actual.sort()
        self.assertListEqual(expected, actual)
        self.assertIn(self.st1, self.st3.parents)
        self.assertIn(self.st2, self.st3.parents)

    def test_delete(self):
        resp = self.client.delete(url_for('api_1_0.steprelationshipparents', step_id=str(self.st3.id)),
                                  json={'parent_step_ids': [str(self.st2.id)]},
                                  headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(dict(parent_step_ids=[]), resp.get_json())
        self.assertEqual(0, len(self.st3.parents))
