from flask import url_for

from dimensigon.domain.entities import Orchestration
from dimensigon.web import db
from tests.base import TestResourceBase


class Test(TestResourceBase):

    def test_orchestration_resource_list(self):
        resp = self.client.get(url_for('api_1_0.orchestrationlist'), headers=self.auth.header)

        self.assertEqual([], resp.get_json())

        o = Orchestration(name='orchestration_name', version=1, description='desc')

        db.session.add(o)
        db.session.commit()

        resp = self.client.get(url_for('api_1_0.orchestrationlist'), headers=self.auth.header)

        self.assertEqual([o.to_json(add_params=True)], resp.get_json())

    def test_orchestration_resource(self):
        resp = self.client.post(url_for('api_1_0.orchestrationlist'),
                                json=dict(name='orchestration_name', description='desc'),
                                headers=self.auth.header)

        self.assertIn('id', resp.get_json())

        o_id = resp.get_json()['id']

        o = Orchestration.query.get(o_id)

        resp = self.client.get(url_for('api_1_0.orchestrationresource', orchestration_id=o_id),
                               headers=self.auth.header)
        db.session.refresh(o)
        self.assertDictEqual(o.to_json(add_params=True), resp.get_json())

        self.assertTrue(o.stop_on_error)
        self.assertTrue(o.stop_undo_on_error)
        resp = self.client.patch(url_for('api_1_0.orchestrationresource', orchestration_id=o_id),
                                 json={"stop_on_error": False},
                                 headers=self.auth.header)
        self.assertEqual(204, resp.status_code)
        db.session.refresh(o)
        self.assertFalse(o.stop_on_error)
        self.assertTrue(o.stop_undo_on_error)
