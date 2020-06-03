from unittest import TestCase

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import ActionTemplate, bypass_datamark_update, Server, User
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client(use_cookies=True)
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        Server.set_initial()
        User.set_initial()
        self.at1_json = {"id": "aaaaaaaa-1234-5678-1234-56781234aaa1",
                         "action_type": "SHELL",
                         "code": "mkdir {dir}",
                         "last_modified_at": "20190101.000530.100000",
                         "expected_output": None,
                         "expected_rc": None,
                         "name": "mkdir",
                         "parameters": {},
                         "system_kwargs": {},
                         "version": 1
                         }
        self.at2_json = {"id": "aaaaaaaa-1234-5678-1234-56781234aaa2",
                         "action_type": "SHELL",
                         "code": "rmdir {dir}",
                         "last_modified_at": "20190101.000530.100000",
                         "expected_output": None,
                         "expected_rc": None,
                         "name": "rmdir",
                         "parameters": {},
                         "system_kwargs": {},
                         "version": 1
                         }

        at1 = ActionTemplate.from_json(self.at1_json)
        at2 = ActionTemplate.from_json(self.at2_json)

        db.session.add_all([at1, at2])
        with bypass_datamark_update():
            db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_action_template_list(self):
        response = self.client.get(url_for('api_1_0.actiontemplatelist'), headers=self.auth.header)

        self.assertListEqual([
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa1",
             "action_type": "SHELL",
             "code": "mkdir {dir}",
             "last_modified_at": "20190101.000530.100000",
             "expected_stdout": None,
             "expected_stderr": None,
             "expected_rc": None,
             "name": "mkdir",
             "parameters": {},
             "system_kwargs": {},
             'post_process': None,
             "version": 1
             },
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa2",
             "action_type": "SHELL",
             "code": "rmdir {dir}",
             "last_modified_at": "20190101.000530.100000",
             "expected_stdout": None,
             "expected_stderr": None,
             "expected_rc": None,
             "name": "rmdir",
             "parameters": {},
             "system_kwargs": {},
             'post_process': None,
             "version": 1
             }
        ], response.get_json())

    def test_action_template(self):
        response = self.client.get(
            url_for('api_1_0.actiontemplateresource', action_template_id="aaaaaaaa-1234-5678-1234-56781234aaa1"),
            headers=self.auth.header)

        self.assertDictEqual(
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa1",
             "action_type": "SHELL",
             "code": "mkdir {dir}",
             "last_modified_at": "20190101.000530.100000",
             "expected_stdout": None,
             "expected_stderr": None,
             "expected_rc": None,
             "name": "mkdir",
             "parameters": {},
             'post_process': None,
             "system_kwargs": {},
             "version": 1
             }, response.get_json())

