from unittest import TestCase

from flask import url_for

from dm.web import create_app


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('dev')
        self.app_context = self.app.app_context()
        self.app_context.push()
        # db.create_all()
        # Role.insert_roles()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self) -> None:
        # db.session.remove()
        # db.drop_all()
        self.app_context.pop()

    def test_action_template_list(self):
        response = self.client.get(url_for('api_1_0.action_template_list'))

        self.assertListEqual([
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa1",
             "action_type": "NATIVE",
             "code": "mkdir {dir}",
             "data_mark": "20190101000530100000",
             "expected_output": None,
             "expected_rc": None,
             "name": "mkdir",
             "parameters": {},
             "system_kwargs": {},
             "version": 1
             },
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa2",
             "action_type": "NATIVE",
             "code": "rmdir {dir}",
             "data_mark": "20190101000530100000",
             "expected_output": None,
             "expected_rc": None,
             "name": "rmdir",
             "parameters": {},
             "system_kwargs": {},
             "version": 1
             }
        ], response.get_json())

    def test_action_template(self):
        response = self.client.get(url_for('api_1_0.action_template', id="aaaaaaaa-1234-5678-1234-56781234aaa1"))

        self.assertDictEqual(
            {"id": "aaaaaaaa-1234-5678-1234-56781234aaa1",
             "action_type": "NATIVE",
             "code": "mkdir {dir}",
             "data_mark": "20190101000530100000",
             "expected_output": None,
             "expected_rc": None,
             "name": "mkdir",
             "parameters": {},
             "system_kwargs": {},
             "version": 1
             }, response.get_json())

    def test_orchestration_list(self):
        response = self.client.get(url_for('api_1_0.orchestration_list'))

        self.assertListEqual([
            {
                "id": "cccccccc-1234-5678-1234-56781234ccc1",
                "name": "create folder",
                "version": 1,
                "description": "Creates a folder on the specified location",
                "steps": ["eeeeeeee-1234-5678-1234-56781234eee1", "eeeeeeee-1234-5678-1234-56781234eee2"],
                "dependencies": {
                    "eeeeeeee-1234-5678-1234-56781234eee1": ["eeeeeeee-1234-5678-1234-56781234eee2"],
                    "eeeeeeee-1234-5678-1234-56781234eee2": []
                },
                "data_mark": "20190101000530100000"
            }
        ], response.get_json())

    def test_orchestration(self):
        self.maxDiff = None
        response = self.client.get(url_for('api_1_0.orchestration', id="cccccccc-1234-5678-1234-56781234ccc1"))

        self.assertDictEqual(
            {
                "id": "cccccccc-1234-5678-1234-56781234ccc1",
                "name": "create folder",
                "version": 1,
                "description": "Creates a folder on the specified location",
                "steps": ["eeeeeeee-1234-5678-1234-56781234eee1", "eeeeeeee-1234-5678-1234-56781234eee2"],
                "dependencies": {
                    "eeeeeeee-1234-5678-1234-56781234eee1": ["eeeeeeee-1234-5678-1234-56781234eee2"],
                    "eeeeeeee-1234-5678-1234-56781234eee2": []
                },
                "data_mark": "20190101000530100000"
            }, response.get_json())

        response = self.client.get(url_for('api_1_0.orchestration',
                                           id="cccccccc-1234-5678-1234-56781234ccc1",
                                           include='steps'))

        self.assertDictEqual(
            {
                "id": "cccccccc-1234-5678-1234-56781234ccc1",
                "name": "create folder",
                "version": 1,
                "description": "Creates a folder on the specified location",
                "steps": [{'action_template': 'aaaaaaaa-1234-5678-1234-56781234aaa1',
                           'data_mark': '20190101000530100000',
                           'id': 'eeeeeeee-1234-5678-1234-56781234eee1',
                           'step_expected_output': None,
                           'step_expected_rc': 0,
                           'step_parameters': {'dir': 'folder'},
                           'step_system_kwargs': None,
                           'stop_on_error': True,
                           'undo': False},
                          {'action_template': 'aaaaaaaa-1234-5678-1234-56781234aaa2',
                           'data_mark': '20190101000530100000',
                           'id': 'eeeeeeee-1234-5678-1234-56781234eee2',
                           'step_expected_output': None,
                           'step_expected_rc': 0,
                           'step_parameters': {'dir': 'folder'},
                           'step_system_kwargs': None,
                           'stop_on_error': True,
                           'undo': True}],
                "dependencies": {
                    "eeeeeeee-1234-5678-1234-56781234eee1": ["eeeeeeee-1234-5678-1234-56781234eee2"],
                    "eeeeeeee-1234-5678-1234-56781234eee2": []
                },
                "data_mark": "20190101000530100000"
            }, response.get_json())
