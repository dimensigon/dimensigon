from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Orchestration, Step, ActionTemplate, ActionType
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db
from tests.base import TestCaseLockBypass


class Test(TestCaseLockBypass):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        self.o = Orchestration(name='name', version=1, description='desc')
        self.at = ActionTemplate(name='action_name', version=1, action_type=ActionType.SHELL, code='')

        db.session.add_all([self.o, self.at])
        set_initial()
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_step_resource_list(self):
        resp = self.client.get(url_for('api_1_0.steplist'), headers=self.auth.header)

        self.assertEqual([], resp.get_json())

        s = self.o.add_step(undo=True, action_template=self.at)
        db.session.add(s)
        db.session.commit()

        resp = self.client.get(url_for('api_1_0.steplist'), headers=self.auth.header)

        self.assertEqual([s.to_json()], resp.get_json())

    def test_step_resources(self):
        resp = self.client.post(url_for('api_1_0.steplist'),
                                json=dict(orchestration_id=str(self.o.id),
                                          undo=False,
                                          action_template_id=str(self.at.id)),
                                headers=self.auth.header)

        self.assertIn('step_id', resp.get_json())

        s_id = resp.get_json()['step_id']

        s = Step.query.get(s_id)

        resp = self.client.get(url_for('api_1_0.stepresource', step_id=s_id),
                               headers=self.auth.header)

        self.assertDictEqual(s.to_json(), resp.get_json())

        self.assertTrue(s.stop_on_error)
        self.assertTrue(s.stop_undo_on_error)
        resp = self.client.patch(url_for('api_1_0.stepresource', step_id=s_id),
                                 json={"stop_on_error": False},
                                 headers=self.auth.header)
        self.assertEqual(204, resp.status_code)
        db.session.refresh(s)
        self.assertFalse(s.stop_on_error)
        self.assertTrue(s.stop_undo_on_error)

        s2 = self.o.add_step(undo=True, action_template=self.at)
        s3 = self.o.add_step(undo=True, action_template=self.at)
        db.session.add_all([s2, s3])
        db.session.commit()

        resp = self.client.patch(url_for('api_1_0.stepresource', step_id=s_id),
                                 json={"child_step_ids": [str(s2.id)]},
                                 headers=self.auth.header)

        self.assertEqual(204, resp.status_code)

        resp = self.client.patch(url_for('api_1_0.stepresource', step_id=str(s3.id)),
                                 json={"parent_step_ids": [str(s.id)]},
                                 headers=self.auth.header)

        self.assertEqual(204, resp.status_code)

        db.session.refresh(s)
        self.assertEqual(2, len(s.children))
        self.assertIn(s2, s.children)
        self.assertIn(s3, s.children)

        resp = self.client.post(url_for('api_1_0.steplist'),
                                json=dict(orchestration_id=str(self.o.id),
                                          undo=False,
                                          action_template_id=str(self.at.id),
                                          parent_step_ids=[s_id],
                                          child_step_ids=[str(s2.id)]),
                                headers=self.auth.header)

        s4: Step = Step.query.get(resp.get_json()['step_id'])

        self.assertEqual(201, resp.status_code)
        self.assertListEqual([s2], s4.children)
        self.assertListEqual([s], s4.parents)

        resp = self.client.put(url_for('api_1_0.stepresource', step_id=str(s4.id)),
                               json=dict(undo=True,
                                         action_template_id=str(self.at.id),
                                         parent_step_ids=[str(s2.id)],
                                         child_step_ids=[str(s3.id)]),
                               headers=self.auth.header)

        db.session.refresh(s4)
        self.assertEqual(204, resp.status_code)
        self.assertListEqual([s2], s4.parents)
        self.assertListEqual([s3], s4.children)

        resp = self.client.delete(url_for('api_1_0.stepresource', step_id=s_id),
                               headers=self.auth.header)

        db.session.expire_all()
        self.assertEqual(204, resp.status_code)
        self.assertIsNone(Step.query.get(s_id))

    def test_step_resource_multiple_steps(self):
        resp = self.client.post(url_for('api_1_0.steplist'),
                                json=[dict(id=1, name="1", orchestration_id=str(self.o.id),
                                           undo=False,
                                           action_template_id=str(self.at.id)),
                                      dict(id=2, name="2", orchestration_id=str(self.o.id),
                                           undo=False,
                                           action_template_id=str(self.at.id),
                                           parent_step_ids=[1]),
                                      dict(id=3, name="3", orchestration_id=str(self.o.id),
                                           undo=False,
                                           action_template_id=str(self.at.id),
                                           parent_step_ids=[2]),
                                      dict(id=4, name="4", orchestration_id=str(self.o.id),
                                           undo=False,
                                           action_template_id=str(self.at.id),
                                           parent_step_ids=[1],
                                           child_step_ids=[3])
                                      ],
                                headers=self.auth.header)

        self.assertEqual(201, resp.status_code)
        db.session.refresh(self.o)
        s1, = self.o.root
        self.assertEqual(0, len(s1.parents))
        self.assertEqual(2, len(s1.children))

        s2, s4 = s1.children

        self.assertEqual(1, len(s2.parents))
        self.assertEqual(1, len(s2.children))

        self.assertEqual(1, len(s4.parents))
        self.assertEqual(1, len(s4.children))
