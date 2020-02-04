from unittest import TestCase

import dm
import elevator
from dm.web import create_app, db
from tests.helpers import initial_test_data


class TestRoot(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        initial_test_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_healthcheck(self):
        response = self.client.get('/healthcheck')
        self.assertDictEqual({"version": dm.__version__,
                              "elevator_version": elevator.__version__,
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


