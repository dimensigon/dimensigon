from unittest import TestCase

import aiohttp
from aiohttp import ClientConnectionError
from aioresponses import aioresponses, CallbackResult
from flask_jwt_extended import create_access_token

import dm.use_cases.exceptions as ue
from dm.domain.entities import Server, Scope, Locker, State, Route, Catalog
from dm.domain.entities.bootstrap import set_initial
from dm.use_cases.lock import lock_unlock, lock
from dm.web import create_app, db


class TestLockUnlock(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

        db.create_all()
        set_initial()

        self.n1 = Server("node1", port=8000)
        Route(self.n1, cost=0)
        self.n2 = Server("node2", port=8000)
        Route(self.n2, cost=0)
        db.session.add_all([self.n1, self.n2])
        db.session.commit()
        self.datamark = Catalog.max_catalog(str)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @aioresponses()
    def test_lock_unlock_lock(self, m):
        def callback_prevent(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'ORCHESTRATION', 'datemark': self.datamark,
                                  'applicant': [str(self.n1.id), str(self.n2.id)]})
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'ORCHESTRATION', 'applicant': [str(self.n1.id), str(self.n2.id)]})
            return CallbackResult("{'message': 'Locked'}", status=200)

        m.post(self.n1.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n1.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(self.n2.url('api_1_0.locker_lock'), callback=callback_lock)

        ret = lock_unlock('L', Scope.ORCHESTRATION, [self.n1, self.n2], applicant=[str(self.n1.id), str(self.n2.id)])

        self.assertIsNone(ret)

    @aioresponses()
    def test_lock_unlock_lock_with_error_on_preventing(self, m):
        m.post(self.n1.url('api_1_0.locker_prevent'), status=200, payload={'message': 'Preventing lock acquired'})
        m.post(self.n2.url('api_1_0.locker_prevent'), status=409, payload={'error': 'Unable to request for lock'})

        with self.assertRaises(ue.ErrorPreventingLock) as e:
            ret = lock_unlock('L', Scope.ORCHESTRATION, [self.n1, self.n2])

        self.assertEqual(Scope.ORCHESTRATION, e.exception.scope)
        self.assertListEqual([ue.ErrorServerLock(self.n2, {'error': 'Unable to request for lock'}, 409)],
                             e.exception.errors)

    @aioresponses()
    def test_lock_unlock_lock_with_server_error_on_preventing(self, m):

        m.post(self.n1.url('api_1_0.locker_prevent'), status=200, payload={'message': 'Preventing lock acquired'})
        m.post(self.n2.url('api_1_0.locker_prevent'), status=500, body="Error message")

        with self.assertRaises(ue.ErrorPreventingLock) as e:
            ret = lock_unlock('L', Scope.ORCHESTRATION, [self.n1, self.n2])

        self.assertEqual(Scope.ORCHESTRATION, e.exception.scope)
        self.assertListEqual([ue.ErrorServerLock(self.n2, "Error message", 500)],
                             e.exception.errors)

    @aioresponses()
    def test_lock_unlock_lock_with_connection_error(self, m):

        m.post(self.n1.url('api_1_0.locker_prevent'), status=200, payload={'message': 'Preventing lock acquired'})
        m.post(self.n2.url('api_1_0.locker_lock'), exception=aiohttp.ClientConnectionError('test'))

        with self.assertRaises(ue.ErrorPreventingLock) as e:
            ret = lock_unlock('L', Scope.ORCHESTRATION, [self.n1, self.n2])

        self.assertEqual(Scope.ORCHESTRATION, e.exception.scope)
        self.assertIsInstance(e.exception.errors[0].msg, aiohttp.ClientConnectionError)
        self.assertIsNone(e.exception.errors[0].code)

    @aioresponses()
    def test_lock_unlock_lock_error_on_lock(self, m):

        m.post(self.n1.url('api_1_0.locker_prevent'), status=200, payload={'message': 'Preventing lock acquired'})
        m.post(self.n2.url('api_1_0.locker_prevent'), status=200, payload={'message': 'Preventing lock acquired'})
        m.post(self.n1.url('api_1_0.locker_lock'), status=200, payload={'message': 'Locked'})
        m.post(self.n2.url('api_1_0.locker_lock'), status=409, payload={'error': 'Unable to lock'})

        with self.assertRaises(ue.ErrorLock) as e:
            ret = lock_unlock('L', Scope.ORCHESTRATION, [self.n1, self.n2])

        self.assertEqual(Scope.ORCHESTRATION, e.exception.scope)
        self.assertListEqual([ue.ErrorServerLock(self.n2, {'error': 'Unable to lock'}, 409)],
                             e.exception.errors)

    @aioresponses()
    def test_lock_unlock_unlock(self, m):
        def callback_unlock(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'ORCHESTRATION', 'applicant': [str(self.n1.id), str(self.n2.id)]})
            return CallbackResult(payload={'message': 'UnLocked'}, status=200)

        m.post(self.n1.url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(self.n2.url('api_1_0.locker_unlock'), callback=callback_unlock)

        ret = lock_unlock('U', Scope.ORCHESTRATION, [self.n1, self.n2])

        self.assertIsNone(ret)

    @aioresponses()
    def test_lock_unlock_unlock_with_error(self, m):
        m.post(self.n2.url('api_1_0.locker_unlock'), status=200, payload={'message': 'UnLocked'})
        m.post(self.n1.url('api_1_0.locker_unlock'), status=409, payload={'error': 'Unable to unlock.'})

        with self.assertRaises(ue.ErrorUnLock) as e:
            ret = lock_unlock('U', Scope.ORCHESTRATION, [self.n1, self.n2], [str(self.n1.id), str(self.n2.id)])

        self.assertEqual(Scope.ORCHESTRATION, e.exception.scope)
        self.assertListEqual([ue.ErrorServerLock(self.n1, {'error': 'Unable to unlock.'}, 409)],
                             e.exception.errors)


class TestLock(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

        db.create_all()
        set_initial()

        self.n1 = Server("node1", port=8000)
        Route(self.n1, cost=0)
        self.n2 = Server("node2", port=8000)
        Route(self.n2, cost=0)
        db.session.add_all([self.n1, self.n2])
        db.session.commit()
        self.datemark = Catalog.max_catalog(str)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_lock_no_server(self):
        with self.assertRaises(RuntimeError):
            ret = lock(Scope.ORCHESTRATION)

    @aioresponses()
    def test_lock_catalog(self, m):
        def callback_prevent(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'CATALOG', 'datemark': self.datemark,
                                  'applicant': [str(Server.get_current().id), str(self.n1.id),
                                                str(self.n2.id)]})
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'CATALOG', 'applicant': [str(Server.get_current().id), str(self.n1.id),
                                                                    str(self.n2.id)]})
            return CallbackResult("{'message': 'Locked'}", status=200)

        m.post(Server.get_current().url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n1.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(Server.get_current().url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(self.n1.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(self.n2.url('api_1_0.locker_lock'), callback=callback_lock)

        applicant = lock(Scope.CATALOG)

        self.assertEqual(applicant, [str(Server.get_current().id), str(self.n1.id), str(self.n2.id)])

    @aioresponses()
    def test_lock_catalog_error_on_preventing(self, m):

        def callback_prevent(url, **kwargs):
            self.assertDictEqual(kwargs['json'],
                                 {'scope': 'CATALOG', 'applicant': [str(Server.get_current().id), str(self.n1.id),
                                                                    str(self.n2.id)]})
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_unlock(url, **kwargs):
            self.assertDictEqual(kwargs['json'], {'scope': 'CATALOG', 'action': 'UNLOCK',
                                                  'applicant': [str(Server.get_current().id), str(self.n1.id),
                                                                str(self.n2.id)]})
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        m.post(Server.get_current().url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n1.url('api_1_0.locker_prevent'), exception=ClientConnectionError())
        m.post(self.n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(Server.get_current().url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(self.n2.url('api_1_0.locker_unlock'), callback=callback_unlock)

        with self.assertRaises(ue.ErrorLock):
            applicant = lock(Scope.CATALOG)

        c = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, c.state)

    @aioresponses()
    def test_lock_unreachable_network(self, m):
        self.n1.route.cost = None
        self.n1.route.gate = None
        self.n1.route.proxy_server = None

        def callback_prevent(url, **kwargs):
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_unlock(url, **kwargs):
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        m.post(Server.get_current().url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(self.n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(Server.get_current().url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(self.n2.url('api_1_0.locker_unlock'), callback=callback_unlock)

        with self.assertRaises(ue.ErrorLock) as e:
            applicant = lock(Scope.CATALOG)

        self.assertDictEqual({'error': 'ErrorPreventingLock', 'servers': [
            {'server_id': str(self.n1.id), 'code': None, 'response': "Unreachable destination 'node1'"}]},
                             e.exception.to_json())
