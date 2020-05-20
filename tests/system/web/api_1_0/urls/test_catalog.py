import datetime
from unittest import TestCase
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token

from dm import defaults
from dm.domain.entities import Server, ActionTemplate, ActionType
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

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.api_1_0.urls.use_cases.get_distributed_entities')
    @patch('dm.domain.entities.get_now')
    def test_catalog(self, mock_now, mock_get):
        mock_now.return_value = datetime.datetime(2019, 4, 2)
        mock_get.return_value = [('ActionTemplate', ActionTemplate)]
        # add data
        s = Server('test', post=8000, me=True)
        db.session.add(s)
        # db.session.commit()

        at1 = ActionTemplate(name='ActionTest1', version=1, action_type=ActionType.ORCHESTRATION, code='')
        db.session.add(at1)

        resp = self.client.get(
            url_for('api_1_0.catalog', data_mark=datetime.datetime(2019, 4, 1).strftime(defaults.DATEMARK_FORMAT)),
            headers=self.headers)

        self.assertDictEqual({'ActionTemplate': [at1.to_json()]},
                             resp.json)

        mock_now.return_value = datetime.datetime(2019, 4, 2, 1)
        at2 = ActionTemplate(name='ActionTest2', version=1, action_type=ActionType.ORCHESTRATION, code='')
        db.session.add(at2)

        resp = self.client.get(
            url_for('api_1_0.catalog', data_mark=datetime.datetime(2019, 4, 2).strftime(defaults.DATEMARK_FORMAT)),
            headers=self.headers)

        self.assertDictEqual({'ActionTemplate': [at2.to_json()]},
                             resp.json)
