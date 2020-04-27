import re
from unittest import TestCase

from aioresponses import aioresponses, CallbackResult
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Scope, Locker, State, Dimension, Route
from dm.domain.entities.bootstrap import set_initial
from dm.use_cases.lock import lock_scope
from dm.utils.helpers import generate_dimension
from dm.web import create_app, db, load_global_data_into_context


class TestLockScope(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
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

    @aioresponses()
    def test_lock_scope(self, m):
        n1 = Server("node1", port=8000)
        Route(n1, cost=0)
        n2 = Server("node2", port=8000)
        Route(n2, cost=0)
        db.session.add_all([n1, n2])
        db.session.commit()

        def callback_prevent(url, **kwargs):
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            return CallbackResult("{'message': 'Locked'}", status=200)

        def callback_unlock(url, **kwargs):
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        def callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # workarround for https://github.com/pnuckowski/aioresponses/issues/111
            headers = {'Authorization': f"Bearer {create_access_token('test')}"}

            r = self.client.post(url.path, json=kwargs['json'], headers=headers)

            return CallbackResult(r.data, status=r.status_code)

        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(n2.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(re.compile(Server.get_current().url() + '.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(n2.url('api_1_0.locker_unlock'), callback=callback_unlock)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

        with self.app.test_request_context('/api/v1.0/lock'):
            with lock_scope(Scope.CATALOG):
                l = Locker.query.get(Scope.CATALOG)
                self.assertEqual(State.LOCKED, l.state)
                self.assertEqual([str(Server.get_current().id), str(n1.id), str(n2.id)], l.applicant)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

    @aioresponses()
    def test_lock_scope_packing(self, m):
        self.app.config['SECURIZER'] = True
        dim = generate_dimension('dimension')
        dim.current = True
        db.session.add(dim)
        n1 = Server("node1", port=8000)
        Route(n1, cost=0)
        n2 = Server("node2", port=8000)
        Route(n2, cost=0)
        db.session.add_all([n1, n2])
        db.session.commit()

        def callback_prevent(url, **kwargs):
            # self.assertDictEqual(kwargs['json'], {'scope': 'CATALOG', 'action': 'PREVENT',
            #                                       'applicant': [str(Server.get_current().id), str(n1.id), str(n2.id)]})
            return CallbackResult("{'message': 'Preventing lock acquired'}", status=200)

        def callback_lock(url, **kwargs):
            # self.assertDictEqual(kwargs['json'], {'scope': 'CATALOG', 'action': 'LOCK',
            #                                       'applicant': [str(Server.get_current().id), str(n1.id), str(n2.id)]})
            return CallbackResult("{'message': 'Locked'}", status=200)

        def callback_unlock(url, **kwargs):
            # self.assertDictEqual(kwargs['json'], {'scope': 'CATALOG', 'action': 'UNLOCK',
            #                                       'applicant': [str(Server.get_current().id), str(n1.id), str(n2.id)]})
            return CallbackResult("{'message': 'UnLocked'}", status=200)

        def callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # workarround for https://github.com/pnuckowski/aioresponses/issues/111
            headers = {'Authorization': f"Bearer {create_access_token('test')}"}

            r = self.client.post(url.path, json=kwargs['json'], headers=headers)

            return CallbackResult(r.data, status=r.status_code)

        m.post(re.compile(Server.get_current().url()+'.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(n2.url('api_1_0.locker_prevent'), callback=callback_prevent)
        m.post(re.compile(Server.get_current().url()+'.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(n2.url('api_1_0.locker_lock'), callback=callback_lock)
        m.post(re.compile(Server.get_current().url()+'.*'), callback=callback_client)
        m.post(n1.url('api_1_0.locker_unlock'), callback=callback_unlock)
        m.post(n2.url('api_1_0.locker_unlock'), callback=callback_unlock)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)

        with self.app.test_request_context('/api/v1.0/lock'):
            load_global_data_into_context()
            with lock_scope(Scope.CATALOG):
                l = Locker.query.get(Scope.CATALOG)
                self.assertEqual(State.LOCKED, l.state)
                self.assertEqual([str(Server.get_current().id), str(n1.id), str(n2.id)], l.applicant)

        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(State.UNLOCKED, l.state)
        self.assertEqual(None, l.applicant)


class TestLockScopeFullChain(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app1 = create_app('test')
        self.app1.config['SERVER_NAME'] = 'node1'
        self.app1.config['SECURIZER'] = True
        self.client1 = self.app1.test_client()
        self.app2 = create_app('test')
        self.app2.config['SERVER_NAME'] = 'node2'
        self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()

        with self.app1.app_context():
            db.create_all()
            set_initial()
            s = Server.get_current()
            s.gates = []
            s.add_new_gate('node1', 8000)
            dim = generate_dimension('dimension')
            dim.current = True
            db.session.add(dim)
            db.session.commit()
            self.s1_json = Server.get_current().to_json()
            self.dim_json = dim.to_json()
            self.headers = {"Authorization": f"Bearer {create_access_token('test')}"}

        with self.app2.app_context():
            db.create_all()
            set_initial()
            s = Server.get_current()
            s.gates = []
            s.add_new_gate('node2', 8000)
            db.session.commit()
            self.s2_json = Server.get_current().to_json()
            s = Server.from_json(self.s1_json)
            s.add_new_gate('node1', 8000)
            Route(s, cost=0)
            db.session.add(s)
            dim = Dimension.from_json(self.dim_json)
            dim.current = True
            db.session.add(dim)
            db.session.commit()

        with self.app1.app_context():
            s = Server.from_json(self.s2_json)
            s.add_new_gate('node2', 8000)
            Route(s, cost=0)
            db.session.add(s)
            db.session.commit()

    def tearDown(self) -> None:
        with self.app1.app_context():
            db.session.remove()
            db.drop_all()

        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

    @aioresponses()
    def test_lock_catalog(self, m):
        def callback_client1(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client1.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult(r.data, status=r.status_code)

        def callback_client2(url, **kwargs):
            kwargs.pop('allow_redirects')
            # passing headers as a workarround for https://github.com/pnuckowski/aioresponses/issues/111
            r = self.client2.post(url.path, json=kwargs['json'], headers=self.headers)

            return CallbackResult(r.data, status=r.status_code)

        m.post(re.compile('https?://node1.*'), callback=callback_client1, repeat=True)
        m.post(re.compile('https?://node2.*'), callback=callback_client2, repeat=True)

        with self.app1.app_context():
            # load dimension into variable
            load_global_data_into_context()
            with self.app1.test_request_context('/api/v1.0/lock'):
                with lock_scope(Scope.CATALOG):
                    l = Locker.query.get(Scope.CATALOG)
                    self.assertEqual(State.LOCKED, l.state)
                    self.assertEqual([self.s1_json['id'], self.s2_json['id']], l.applicant)
