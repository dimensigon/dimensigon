from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Orchestration
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

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_orchestration_resource_list(self):
        resp = self.client.get(url_for('api_1_0.orchestrationlist'), headers=self.auth.header)

        self.assertEqual([], resp.get_json())

        o = Orchestration(name='orchestration_name', version=1, description='desc')

        db.session.add(o)
        db.session.commit()

        resp = self.client.get(url_for('api_1_0.orchestrationlist'), headers=self.auth.header)

        self.assertEqual([o.to_json(add_target=True, add_params=True)], resp.get_json())

    def test_orchestration_resource(self):
        resp = self.client.post(url_for('api_1_0.orchestrationlist'),
                                json=dict(name='orchestration_name',
                                          version=1, description='desc'),
                                headers=self.auth.header)

        self.assertIn('orchestration_id', resp.get_json())

        o_id = resp.get_json()['orchestration_id']

        o = Orchestration.query.get(o_id)

        resp = self.client.get(url_for('api_1_0.orchestrationresource', orchestration_id=o_id),
                               headers=self.auth.header)

        self.assertDictEqual(o.to_json(add_target=True, add_params=True), resp.get_json())

        self.assertTrue(o.stop_on_error)
        self.assertTrue(o.stop_undo_on_error)
        resp = self.client.patch(url_for('api_1_0.orchestrationresource', orchestration_id=o_id),
                                 json={"stop_on_error": False},
                                 headers=self.auth.header)
        self.assertEqual(204, resp.status_code)
        self.assertFalse(o.stop_on_error)
        self.assertTrue(o.stop_undo_on_error)
