import re
from unittest import TestCase, mock

from aioresponses import aioresponses, CallbackResult
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Server, Scope, Locker, State, Dimension, Route
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.domain.entities.user import ROOT
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import create_app, db, load_global_data_into_context
from tests.base import TestDimensigonBase, TwoNodeMixin, ThreeNodeMixin, VirtualNetworkMixin


class TestLockScope(ThreeNodeMixin, TestCase):

    @mock.patch('dimensigon.web.helpers.current_app')
    @aioresponses()
    def test_lock_scope(self, mock_app, m):

        mock_app.dm.cluster_manager.get_alive.return_value = [self.s2.id, self.s3.id]

        def callback_prevent(url, **kwargs):
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            return CallbackResult("{'message': 'Locked'}", status=200)

        def callback_unlock(url, **kwargs):
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        def callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # workarround for https://github.com/pnuckowski/aioresponses/issues/111
            headers = {'Authorization': f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

            r = self.client.post(url.path, json=kwargs['json'], headers=headers)

            return CallbackResult(r.data, status=r.status_code)

        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.s3.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(self.s3.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(self.s3.url('api_1_0.locker_unlock'), callback=callback_unlock)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

        with self.app.test_request_context('/api/v1.0/lock'):
            with lock_scope(Scope.CATALOG, identity=ROOT):
                l = Locker.query.get(Scope.CATALOG)
                self.assertEqual(State.LOCKED, l.state)
                self.assertEqual([str(Server.get_current().id), str(self.s2.id), str(self.s3.id)], l.applicant)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

    @mock.patch('dimensigon.web.helpers.current_app')
    @aioresponses()
    def test_lock_scope_packing(self, mock_app, m):

        mock_app.dm.cluster_manager.get_alive.return_value = [self.s2.id, self.s3.id]

        def callback_prevent(url, **kwargs):
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            return CallbackResult("{'message': 'Locked'}", status=200)

        def callback_unlock(url, **kwargs):
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        def callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # workarround for https://github.com/pnuckowski/aioresponses/issues/111
            headers = {'Authorization': f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

            r = self.client.post(url.path, json=kwargs['json'], headers=headers)

            return CallbackResult(r.data, status=r.status_code)

        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.s3.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(self.s3.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(self.s2.url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(self.s3.url('api_1_0.locker_unlock'), callback=callback_unlock)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

        with self.app.test_request_context('/api/v1.0/lock'):
            load_global_data_into_context()
            with lock_scope(Scope.CATALOG, identity=ROOT):
                l = Locker.query.get(Scope.CATALOG)
                self.assertEqual(State.LOCKED, l.state)
                self.assertEqual([str(Server.get_current().id), str(self.s2.id), str(self.s3.id)], l.applicant)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)


class TestLockScopeFullChain(VirtualNetworkMixin, TwoNodeMixin, TestCase):

    @mock.patch('dimensigon.web.helpers.current_app')
    def test_lock_catalog(self, mock_app):
        mock_app.dm.cluster_manager.get_alive.return_value = [self.s1.id, self.s2.id]

        # load dimension into variable
        with self.app.test_request_context('/api/v1.0/lock'):
            load_global_data_into_context()
            with lock_scope(Scope.CATALOG, identity=ROOT):
                l = Locker.query.get(Scope.CATALOG)
                self.assertEqual(State.LOCKED, l.state)
                self.assertEqual([self.s1.id, self.s2.id], l.applicant)
