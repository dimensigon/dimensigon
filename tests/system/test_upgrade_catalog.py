import datetime
import re
import uuid
from unittest import TestCase
from unittest.mock import patch

import responses
from flask_jwt_extended import create_access_token

import dm.use_cases.exceptions as ue
from dm.domain.entities import Server, ActionTemplate, ActionType, Catalog, Gate, Route
from dm.domain.entities.bootstrap import set_initial
from dm.use_cases.interactor import upgrade_catalog_from_server
from dm.web import create_app, db


class TestUpgradeCatalog(TestCase):

    @patch('dm.domain.entities.get_now')
    def setUp(self, mock_now):
        """Create and configure a new app instance for each test."""
        mock_now.return_value = datetime.datetime(2019, 4, 1, 0)

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

    @patch('dm.domain.entities.get_now')
    @patch('dm.use_cases.interactor.get_distributed_entities')
    @patch('dm.use_cases.interactor.lock_scope')
    @responses.activate
    def test_upgrade_catalog(self, mock_lock, mock_entities, mock_now):
        mock_lock.return_value.__enter__.return_value = 'applicant'
        mock_entities.return_value = [('ActionTemplate', ActionTemplate), ('Server', Server), ('Gate', Gate)]
        mock_now.return_value = datetime.datetime(2019, 4, 1, 0)

        at1 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'), name='mkdir', version=1,
                             action_type=ActionType.NATIVE,
                             code='mkdir {dir}', parameters={}, expected_output=None, expected_rc=None,
                             system_kwargs={})
        db.session.add(at1)
        db.session.commit()

        s = Server(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234bbb1'), name='server',
                   last_modified_at=datetime.datetime(2019, 4, 1, 0))
        s_json = s.to_json()
        g = Gate(server=s, port=80, dns='server', last_modified_at=datetime.datetime(2019, 4, 1, 0))
        g_json = g.to_json()
        Route(s, cost=0)

        at2 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa2'), name='rmdir', version=1,
                             action_type=ActionType.NATIVE,
                             code='rmdir {dir}', parameters={}, expected_output=None, expected_rc=None,
                             system_kwargs={}, last_modified_at=datetime.datetime(2019, 4, 1, 1))
        at2_json = at2.to_json()
        del at2

        at1_json = at1.to_json()
        del at1
        at1_json['code'] = 'mkdir -p {dir}'
        responses.add(method='GET',
                      url=re.compile('^' + s.url('api_1_0.catalog', data_mark='12345').replace('12345', '')),
                      json={"ActionTemplate": [at1_json, at2_json], "Server": [s_json], "Gate": [g_json]})

        upgrade_catalog_from_server(s)

        atl = [at.to_json() for at in ActionTemplate.query.all()]

        self.assertListEqual([at1_json, at2_json], atl)

        c = Catalog.query.get('ActionTemplate')
        self.assertEqual(datetime.datetime(2019, 4, 1, 1), c.last_modified_at)

        at1 = ActionTemplate.query.get('aaaaaaaa-1234-5678-1234-56781234aaa1')
        self.assertEqual('mkdir -p {dir}', at1.code)

    # no new data
    @patch('dm.use_cases.interactor.get_distributed_entities')
    @patch('dm.use_cases.interactor.lock_scope')
    @responses.activate
    def test_upgrade_catalog_no_data(self, mock_lock, mock_entities):
        mock_lock.return_value.__enter__.return_value = 'applicant'
        mock_entities.return_value = [('ActionTemplate', ActionTemplate)]

        s = Server('server', last_modified_at=datetime.datetime(2019, 4, 1, 0))
        g = Gate(server=s, port=80)
        Route(s, cost=0)

        responses.add(method='GET',
                      url=re.compile('^' + s.url('api_1_0.catalog', data_mark='12345').replace('12345', '')),
                      json={"ActionTemplate": []})

        upgrade_catalog_from_server(s)

        atl = [at.to_json() for at in ActionTemplate.query.all()]

        self.assertEqual(0, len(atl))

    @patch('dm.use_cases.interactor.get_distributed_entities')
    @patch('dm.use_cases.interactor.lock_scope')
    @responses.activate
    def test_upgrade_catalog_catalog_mismatch(self, mock_lock, mock_entities):
        mock_lock.return_value.__enter__.return_value = 'applicant'
        mock_entities.return_value = [('ActionTemplate', ActionTemplate), ('Server', Server)]

        s = Server('server', last_modified_at=datetime.datetime(2019, 4, 1, 0), port=8000)
        Route(s, cost=0)

        at1 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa1'), name='mkdir', version=1,
                             action_type=ActionType.NATIVE,
                             code='mkdir {dir}', parameters={}, expected_output=None, expected_rc=None,
                             system_kwargs={}, last_modified_at=datetime.datetime(2019, 4, 1, 0))

        at2 = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-56781234aaa2'), name='rmdir', version=1,
                             action_type=ActionType.NATIVE,
                             code='rmdir {dir}', parameters={}, expected_output=None, expected_rc=None,
                             system_kwargs={}, last_modified_at=datetime.datetime(2019, 4, 1, 1))

        responses.add(method='GET',
                      url=re.compile('^' + s.url('api_1_0.catalog', data_mark='12345').replace('12345', '')),
                      json={"ActionTemplate": [at1.to_json(), at2.to_json()]})

        with self.assertRaises(ue.CatalogMismatch):
            upgrade_catalog_from_server(s)
