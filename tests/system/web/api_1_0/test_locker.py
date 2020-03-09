import threading
from unittest import TestCase, mock

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities.bootstrap import set_initial
from dm.domain.entities.locker import Scope, State, Locker
from dm.web import create_app, db


class TestApi(TestCase):
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

        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='PREVENT',
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
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='PREVENT',
                                          applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        locker_mod.revert_preventing.assert_called_once()

        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.PREVENTING)

        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='PREVENT', applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='PREVENT', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.CATALOG.name, action='PREVENT', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.UPGRADE.name, action='PREVENT', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.UPGRADE)
        self.assertEqual(l.state, State.PREVENTING)

        # LOCK
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='LOCK', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='LOCK', applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.LOCKED)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.CATALOG.name, action='LOCK', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.UPGRADE.name, action='LOCK', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.UPGRADE)
        self.assertEqual(l.state, State.LOCKED)

        # UNLOCK
        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='UNLOCK', applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker'),
                                json=dict(scope=Scope.ORCHESTRATION.name, action='UNLOCK', applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.UNLOCKED)
