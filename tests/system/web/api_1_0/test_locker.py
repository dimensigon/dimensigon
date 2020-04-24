import threading
from unittest import TestCase, mock

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Catalog
from dm.domain.entities.bootstrap import set_initial
from dm.domain.entities.locker import Scope, State, Locker
from dm.web import create_app, db


class TestLocker(TestCase):
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
        self.datemark = Catalog.max_catalog(str)

        import dm.web.api_1_0.urls.locker as locker_mod
        self.revert_preventing = locker_mod.revert_preventing

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        import dm.web.api_1_0.urls.locker as locker_mod
        locker_mod.revert_preventing = self.revert_preventing

    def test_lock_timer(self):
        import dm.web.api_1_0.urls.locker as locker_mod

        locker_mod.defaults.TIMEOUT_PREVENTING_LOCK = 0.01

        event = threading.Event()

        def set_event_on_done(func):
            def wrapper(*args, **kwargs):
                func(*args, **kwargs)
                event.set()

            return wrapper

        locker_mod.revert_preventing = set_event_on_done(locker_mod.revert_preventing)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant='applicant'),
                                headers=self.headers)

        event.wait()

        l = Locker.query.get(Scope.ORCHESTRATION)

        self.assertEqual(State.UNLOCKED, l.state)

    def test_lock(self):
        import dm.web.api_1_0.urls.locker as locker_mod

        locker_mod.defaults.TIMEOUT_PREVENTING_LOCK = 0
        revert_preventing = locker_mod.revert_preventing
        locker_mod.revert_preventing = mock.Mock()
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        locker_mod.revert_preventing.assert_called_once()

        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.PREVENTING)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.UPGRADE.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.UPGRADE)
        self.assertEqual(l.state, State.PREVENTING)

        # LOCK
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.LOCKED)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.CATALOG.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.UPGRADE)
        self.assertEqual(l.state, State.LOCKED)

        # UNLOCK
        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.UNLOCKED)

    def test_lock_datemark(self):
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark='19000101.000000.000000',
                                          applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)
        self.assertEqual(f"Old catalog datemark. Upgrade Catalog to {self.datemark} to lock", resp.get_json()['error'])
