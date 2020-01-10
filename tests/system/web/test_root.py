from unittest import TestCase, mock

import requests

from dm.web import create_app, db, set_variables
from tests.helpers import initial_test_data


class TestRoot(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('dev')

        with self.app.app_context():
            db.create_all()
            set_variables()
            initial_test_data()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.drop_all()

    def test_healthcheck(self):
        client = self.app.test_client()
        response = client.get('/healthcheck')

        self.assertDictEqual({"version": "0.0.1",
                              "elevator_version": "0.0.1",
                              "catalog_version": "20190101000530100000",
                              "neighbours": [],
                              "services": [
                                  {
                                      "service1": {
                                          "status": "ALIVE"
                                      }
                                  }
                              ]
                              }, response.get_json())