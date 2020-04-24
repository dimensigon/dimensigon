from unittest import TestCase

from flask import url_for
from flask_jwt_extended import create_access_token

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

    def test_json_validation_error(self):
        resp = self.client.post(url_for('api_1_0.locker_prevent'), json={}, headers=self.headers)

        self.assertIn('error', resp.json)
        self.assertTrue(resp.json['error'].startswith("'scope' is a required property"))
