from unittest import TestCase

from dateutil.tz import tzlocal
from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import ActionTemplate, bypass_datamark_update, Server, User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db


class TestActionTemplate(TestCase):
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
                         "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT),
                         "name": "mkdir",
                         "version": 1
                         }
        self.at2_json = {"id": "aaaaaaaa-1234-5678-1234-56781234aaa2",
                         "action_type": "SHELL",
                         "code": "rmdir {dir}",
                         "last_modified_at": defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT),
                         "expected_stdout": 'output',
                         "expected_stderr": 'err',
                         "expected_rc": 0,
                         "name": "rmdir",
                         "parameters": {'param1': 1},
                         "system_kwargs": {'kwarg1': 1},
                         'pre_process': 'pre_process',
                         'post_process': 'post_process',
                         "version": 1
                         }

        with bypass_datamark_update():
            at1 = ActionTemplate.from_json(self.at1_json)
            at2 = ActionTemplate.from_json(self.at2_json)

            db.session.add_all([at1, at2])
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
             "last_modified_at": defaults.INITIAL_DATEMARK.astimezone(tzlocal()).strftime(defaults.DATEMARK_FORMAT),
             "name": "mkdir",
             "version": 1
             },
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa2",
             "action_type": "SHELL",
             "code": "rmdir {dir}",
             "last_modified_at": defaults.INITIAL_DATEMARK.astimezone(tzlocal()).strftime(defaults.DATEMARK_FORMAT),
             "expected_stdout": 'output',
             "expected_stderr": 'err',
             "expected_rc": 0,
             "name": "rmdir",
             "parameters": {'param1': 1},
             "system_kwargs": {'kwarg1': 1},
             'pre_process': 'pre_process',
             'post_process': 'post_process',
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
             "last_modified_at": defaults.INITIAL_DATEMARK.astimezone(tzlocal()).strftime(defaults.DATEMARK_FORMAT),
             "name": "mkdir",
             "version": 1
             }, response.get_json())

