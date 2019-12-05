import copy
import datetime
import json
import pickle
from unittest import TestCase, mock

import requests
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure

from config import Config
import dm
from dm.network.gateway import generate_msg
from dm.use_cases.exceptions import CatalogMismatch, CommunicationError

from dm.utils.helpers import encode, encode
from dm.web import create_app, catalog_manager, repo_manager, interactor
from tests.system.data import Server1, Server2, delta


class TestUpgradeCatalog(TestCase):

    def setUp(self) -> None:
        self.app1 = create_app(Server1())
        self.app2 = create_app(Server2())

        self.client1 = self.app1.test_client()
        self.client2 = self.app2.test_client()


    def test_upgrade_catalog_server(self):
        self.maxDiff = None
        with mock.patch('dm.network.gateway.requests.post') as mocked_post:
            generate_msg(destination='bbbbbbbb-1234-5678-1234-56781234bbb2',
                         source='bbbbbbbb-1234-5678-1234-56781234bbb1',
                         data=dict(function='local_get_delta_catalog', data_mark='20190101000530100000'))
            data, key = encode()
            resp = self.client2.post('/socket', json={'destination': 'bbbbbbbb-1234-5678-1234-56781234bbb2',
                                                      'source':
                                                      'data': data})

            self.assertDictEqual(delta, resp.get_json())

    def test_upgrade_catalog_client(self):
        with mock.patch('dm.network.gateway.requests.post') as mocked_post:
            # Set response for request
            response = requests.Response()
            response.url = 'http://server2.localdomain:80/socket?'
            response.headers = {'User-Agent': 'werkzeug/0.16.0', 'Content-Type': 'application/json'}
            response.status_code = 200
            response._content = json.dumps(delta).encode()
            mocked_post.return_value = response
            # set which classes to upgrade
            repo_manager._repo_classes = {'ActionTemplateRepo': dm.repositories.ActionTemplateRepo,
                                  'CatalogRepo': dm.repositories.CatalogRepo,
                                          # 'LogRepo': dm.repositories.LogRepo,
                                  'OrchestrationRepo': dm.repositories.OrchestrationRepo,
                                  'ServerRepo': dm.repositories.ServerRepo,
                                  'ServiceRepo': dm.repositories.ServiceRepo,
                                  'StepRepo': dm.repositories.StepRepo}
            with self.app1.app_context():
                interactor.lock = mock.Mock(return_value=Success(None))
                interactor.unlock = mock.Mock(return_value=Success(None))
                server = repo_manager.ServerRepo.find(id_='bbbbbbbb-1234-5678-1234-56781234bbb2')
                res = interactor.upgrade_catalog(server)
                self.assertIsInstance(res, Result)
                e = res.failure()
                if not isinstance(e, CatalogMismatch):
                    raise e
                self.assertIn('ServiceRepo', e.args[0])

                d = dict(delta)
                d.update({'ServiceRepo': []})
                response._content = json.dumps(d).encode()

                res = interactor.upgrade_catalog(server)
                if not is_successful(res):
                    res.failure()

                action_list = repo_manager.ActionTemplateRepo.all()
                self.assertEqual(4, len(action_list))
                action = repo_manager.ActionTemplateRepo.find(id_='aaaaaaaa-1234-5678-1234-56781234aaa1')

                self.assertEqual(datetime.datetime.strptime('20190101000532100000', '%Y%m%d%H%M%S%f'),
                                 action.data_mark)

                self.assertListEqual([
                    datetime.datetime.strptime('20190101000532100000', '%Y%m%d%H%M%S%f'),
                    datetime.datetime.strptime('20190101000533100000', '%Y%m%d%H%M%S%f'),
                    datetime.datetime.strptime('20190101000534100000', '%Y%m%d%H%M%S%f'),
                    datetime.datetime.strptime('20190101000530200000', '%Y%m%d%H%M%S%f')],
                    catalog_manager._data_mark)


                response.status_code = 404
                response.reason = "Not Found"
                res = interactor.upgrade_catalog(server)
                e = res.failure()
                if not isinstance(e, requests.exceptions.HTTPError):
                    raise e