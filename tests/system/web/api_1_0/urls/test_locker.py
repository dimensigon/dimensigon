import time
from unittest import TestCase, mock
from unittest.mock import patch

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Catalog
from dm.domain.entities.bootstrap import set_initial
from dm.domain.entities.locker import State, Locker, Scope
from dm.web import create_app, db


class TestLocker(TestCase):
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
        db.session.commit()
        self.datemark = Catalog.max_catalog(str)

        import dm.web.api_1_0.urls.locker as locker_mod
        self.revert_preventing = locker_mod.revert_preventing

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.api_1_0.urls.locker.defaults.TIMEOUT_PREVENTING_LOCK', 0.01)
    def test_lock_prevent_timer(self):


        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)

        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.PREVENTING)

        start = time.time()
        while time.time() - start < 5:
            db.session.expire(l)
            if l.state == State.UNLOCKED:
                start -= 5
            else:
                time.sleep(0.01)

        self.assertEqual(State.UNLOCKED, l.state)

    @mock.patch('dm.web.api_1_0.urls.locker.threading')
    def test_lock(self, mock_thread):


        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.headers)

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
                                json=dict(scope=Scope.UPGRADE.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.CATALOG)
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
                                json=dict(scope=Scope.UPGRADE.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.CATALOG.name, applicant='applicant2'),
                                headers=self.headers)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.CATALOG)
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

