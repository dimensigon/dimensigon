import datetime as dt
import os
import re
import threading
from unittest import TestCase, mock
from unittest.mock import patch

import responses
from aioresponses import aioresponses

from dimensigon import defaults
from dimensigon.domain.entities import Server, Catalog, Software, ActionTemplate, ActionType, SoftwareServerAssociation
from dimensigon.use_cases.catalog import CatalogManager, NewVersionFound, NoServerFound, CatalogFetchError
from dimensigon.web import db
from dimensigon.web.api_1_0.urls.use_cases import fetch_catalog
from tests.base import TwoNodeMixin, LockBypassMixin

basedir = os.path.abspath(os.path.dirname(__file__))
now1 = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
now2 = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
now3 = dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc)


@patch('dimensigon.use_cases.catalog.__version__', '1')
class TestCatalog(LockBypassMixin, TwoNodeMixin, TestCase):

    @patch('dimensigon.domain.entities.get_now')
    def setUp(self, mocked_now):
        self.initials = dict(self.initials)
        self.initials.update(action_template=False)
        mocked_now.return_value = now1
        super().setUp()
        with self.app2_context:
            mocked_now.return_value = now2
            soft = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='test', version='1', filename='file')
            at = ActionTemplate(id='aaaaaaaa-1234-5678-1234-56781234aaa2', name='mkdir', version=1,
                                action_type=ActionType.SHELL, code='mkdir {dir}')
            db.session.add_all([soft, at])
            db.session.commit()
            mocked_now.return_value = now3
            ssa = SoftwareServerAssociation(software=soft, server=Server.get_current(), path='/root')
            db.session.add(ssa)
            db.session.commit()
            self.soft_json = soft.to_json()
            self.at_json = at.to_json()
            self.catalog = fetch_catalog(now1)

        self.mock_queue = mock.Mock()
        self.mock_dm = mock.Mock()
        self.mock_dm.flask_app = self.app
        self.mock_dm.engine = db.engine
        self.mock_dm.manager.dict.return_value = dict()
        self.mock_dm.server_id = self.s1.id

        self.cm = CatalogManager("Catalog", startup_event=threading.Event(), shutdown_event=threading.Event(),
                                 publish_q=self.mock_queue, event_q=None, dimensigon=self.mock_dm)
        db.session.commit()

    @responses.activate
    @aioresponses()
    def test_catalog(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'),
               status=200, payload=dict(server=dict(id=self.s2.id, name=self.s2.name),
                                        version='1',
                                        catalog_version=now3.strftime(defaults.DATEMARK_FORMAT)))
        'https://node2:5000/api/v1.0/catalog/20190401.000000.000000%2B0000'
        responses.add(responses.GET, re.compile(
            r'https?://node2:\d+/api/v1\.0/catalog/' + now1.strftime(defaults.DATEMARK_FORMAT).replace('+', '%2B')),
                      json=self.catalog, status=200)

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.app2_context:
            self.assertEqual(6, Catalog.query.count())
            self.assertEqual(defaults.INITIAL_DATEMARK, Catalog.query.get('User').last_modified_at)
            self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)
            self.assertEqual(now1, Catalog.query.get('Gate').last_modified_at)
            self.assertEqual(now2, Catalog.query.get('Software').last_modified_at)
            self.assertEqual(now3, Catalog.query.get('SoftwareServerAssociation').last_modified_at)
            self.assertEqual(now2, Catalog.query.get('ActionTemplate').last_modified_at)

        self.cm.upgrade_process()

        soft = Software.query.get('aaaaaaaa-1234-5678-1234-56781234aaa1')
        self.assertDictEqual(self.soft_json, soft.to_json())
        soft = ActionTemplate.query.get('aaaaaaaa-1234-5678-1234-56781234aaa2')
        self.assertDictEqual(self.at_json, soft.to_json())

        self.assertEqual(6, Catalog.query.count())
        self.assertEqual(defaults.INITIAL_DATEMARK, Catalog.query.get('User').last_modified_at)
        self.assertEqual(now2, Catalog.query.get('Software').last_modified_at)
        self.assertEqual(now3, Catalog.query.get('SoftwareServerAssociation').last_modified_at)
        self.assertEqual(now2, Catalog.query.get('ActionTemplate').last_modified_at)
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)
        self.assertEqual(now1, Catalog.query.get('Gate').last_modified_at)

    @responses.activate
    @aioresponses()
    def test_catalog_no_response_from_neighbour(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'), status=400)

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.assertRaises(NoServerFound):
            self.cm.upgrade_process()

    @responses.activate
    @aioresponses()
    def test_catalog_mayor_version_found(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'),
               status=200, payload=dict(server=dict(id=self.s2.id, name=self.s2.name),
                                        version='2',
                                        catalog_version=now3.strftime(defaults.DATEMARK_FORMAT)))

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.assertRaises(NewVersionFound):
            self.cm.upgrade_process()

    @responses.activate
    @aioresponses()
    def test_catalog_no_server_with_high_catalog(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'),
               status=200, payload=dict(server=dict(id=self.s2.id, name=self.s2.name),
                                        version='1',
                                        catalog_version=now1.strftime(defaults.DATEMARK_FORMAT)))

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.assertRaises(NoServerFound):
            self.cm.upgrade_process()

    @responses.activate
    @aioresponses()
    def test_catalog_error_fetching_catalog(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'),
               status=200, payload=dict(server=dict(id=self.s2.id, name=self.s2.name),
                                        version='1',
                                        catalog_version=now3.strftime(defaults.DATEMARK_FORMAT)))
        'https://node2:5000/api/v1.0/catalog/20190401.000000.000000%2B0000'
        responses.add(responses.GET, re.compile(
            r'https?://node2:\d+/api/v1\.0/catalog/' + now1.strftime(defaults.DATEMARK_FORMAT).replace('+', '%2B')),
                      status=400)

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.assertRaises(CatalogFetchError):
            self.cm.upgrade_process()

    @responses.activate
    @aioresponses()
    def test_catalog_healthcheck_server_mismatch(self, m):
        # set response for fetching catalog on node
        m.post(re.compile(r'https?://node2:\d+/healthcheck'),
               status=200, payload=dict(server=dict(id=1, name=self.s2.name),
                                        version='1',
                                        catalog_version=now3.strftime(defaults.DATEMARK_FORMAT)))
        'https://node2:5000/api/v1.0/catalog/20190401.000000.000000%2B0000'
        responses.add(responses.GET, re.compile(
            r'https?://node2:\d+/api/v1\.0/catalog/' + now1.strftime(defaults.DATEMARK_FORMAT).replace('+', '%2B')),
                      status=400)

        self.assertListEqual([('Gate',), ('Server',), ('User',)],
                             db.session.query(Catalog.entity).order_by(Catalog.entity).all())
        self.assertEqual(now1, Catalog.query.get('Server').last_modified_at)

        with self.assertRaises(NoServerFound):
            self.cm.upgrade_process()