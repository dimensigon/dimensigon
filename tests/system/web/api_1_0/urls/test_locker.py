import datetime as dt
import time
from unittest import TestCase, mock
from unittest.mock import patch

from flask import url_for

from dimensigon import defaults
from dimensigon.domain.entities import Catalog
from dimensigon.domain.entities.locker import State, Locker, Scope
from dimensigon.web import db
from tests.base import OneNodeMixin


class TestLocker(OneNodeMixin, TestCase):

    def setUp(self) -> None:
        super().setUp()

        self.datemark = Catalog.max_catalog(str)

        import dimensigon.web.api_1_0.urls.locker as locker_mod
        self.revert_preventing = locker_mod.revert_preventing

    @patch('dimensigon.web.api_1_0.urls.locker.defaults.TIMEOUT_PREVENTING_LOCK', 0.01)
    def test_lock_prevent_timer(self):

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.auth.header)

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

    @mock.patch('dimensigon.web.api_1_0.urls.locker.threading')
    def test_lock(self, mock_thread):

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.auth.header)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark,
                                          applicant=['applicant']),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark,
                                          applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.UPGRADE.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        l = Locker.query.get(Scope.CATALOG)
        l.applicant = None
        l.state = State.UNLOCKED

        l = Locker.query.get(Scope.ORCHESTRATION)
        l.applicant = ['applicant']
        l.state = State.PREVENTING
        db.session.commit()

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.CATALOG.name, datemark=self.datemark, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(l.state, State.PREVENTING)

        # LOCK
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant=['applicant']),
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.LOCKED)

        # LOWER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        # HIGHER PRIORITY LOCKER
        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.CATALOG.name, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.CATALOG)
        self.assertEqual(l.state, State.LOCKED)

        # UNLOCK
        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant='applicant2'),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant=['applicant']),
                                headers=self.auth.header)

        self.assertEqual(200, resp.status_code)
        l = Locker.query.get(Scope.ORCHESTRATION)
        self.assertEqual(l.state, State.UNLOCKED)

    def test_lock_datemark(self):
        datemark = defaults.INITIAL_DATEMARK - dt.timedelta(seconds=1)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name,
                                          datemark=datemark.strftime(defaults.DATEMARK_FORMAT),
                                          applicant=['applicant']),
                                headers=self.auth.header)

        self.assertEqual(409, resp.status_code)

    def test_lock_orchestration(self):
        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        l = Locker.query.get(Scope.ORCHESTRATION)
        l.state = State.PREVENTING
        l.applicant = "1"
        db.session.commit()
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        l.state = State.LOCKED
        db.session.commit()

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.ORCHESTRATION.name, datemark=self.datemark, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.ORCHESTRATION.name, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

    def test_lock_upgrade_multiple_times(self):
        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.UPGRADE.name, datemark=self.datemark, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_prevent'),
                                json=dict(scope=Scope.UPGRADE.name, datemark=self.datemark, applicant="2"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_lock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant="2"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant="1"),
                                headers=self.auth.header)
        self.assertEqual(210, resp.status_code)

        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(scope=Scope.UPGRADE.name, applicant="2"),
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

    def test_lock_upgrade_unlock_force(self):
        from dimensigon.web.api_1_0.urls.locker import counter
        counter.value = 2

        l = Locker.query.get(Scope.UPGRADE)
        l.state = State.LOCKED

        resp = self.client.post(url_for('api_1_0.locker_unlock'),
                                json=dict(force=True, scope=Scope.UPGRADE.name, applicant="2"),
                                headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        self.assertEqual(0, counter.value)
        db.session.refresh(l)
        self.assertEqual(State.UNLOCKED, l.state)
