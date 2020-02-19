import datetime
import typing as t
import uuid

from asynctest import TestCase, mock
from dm.domain.catalog_manager import CatalogManager
from returns.pipeline import is_successful

import dm.network.exceptions as ne
import dm.use_cases.exceptions as ue
from dm.domain.entities import Server
from dm.domain.locker import LockState, UnlockState
from dm.use_cases.base import Scope
from dm.use_cases.interactor import Interactor

if t.TYPE_CHECKING:
    from returns.result import Result


class TestInteractor(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.s1 = Server(name='Server1', ip='127.0.0.1', port=5001, route=[],
                        id=uuid.UUID('12345678-1234-5678-1234-567812345678'))
        cls.s2 = Server(name='Server2', ip='127.0.0.1', port=5002, route=[],
                        id=uuid.UUID('22345678-1234-5678-1234-567812345678'))
        cls.s3 = Server(name='Server3', ip='127.0.0.1', port=5003, route=[cls.s2],
                        id=uuid.UUID('32345678-1234-5678-1234-567812345678'))
        cls.s4 = Server(name='Server4', ip='127.0.0.1', port=5004, route=[cls.s2, cls.s3],
                        id=uuid.UUID('42345678-1234-5678-1234-567812345678'))
        cls.servers = [cls.s1, cls.s2, cls.s3, cls.s4]
        cls.server = mock.MagicMock()
        cls.server.id.return_value = 'test_server'

    def setUp(self) -> None:
        # self.i: t.Optional[Interactor] = None  # Interactor to generate in every Test

        self.i = Interactor(catalog=CatalogManager(datetime.datetime), server=self.s1)

    def tearDown(self) -> None:
        if self.i:
            self.i.stop_timer()
        self.i = None

    def test_lock_unlock_mechanism(self):
        with mock.patch('dm.network.gateway.async_send_message', return_value=('', 200)) as mocked_send:
            r = self.i.lock(scope=Scope.ORCHESTRATION, servers=self.servers)

            self.assertTrue(is_successful(r))
            self.assertEqual(8, mocked_send.call_count)
            self.assertIsInstance(self.i.lockers[Scope.ORCHESTRATION].state, LockState)

            r = self.i.unlock(scope=Scope.ORCHESTRATION)

            self.assertTrue(is_successful(r))
            self.assertEqual(12, mocked_send.call_count)
            self.assertIsInstance(self.i.lockers[Scope.ORCHESTRATION].state, UnlockState)

    def test_lock_unlock_errors(self):
        r: Result = self.i.lock(scope=Scope.ORCHESTRATION)
        self.assertFalse(is_successful(r))
        self.assertIsInstance(r.failure(), ue.ServersMustNotBeBlank)

        side_effect = [('', 200), ('', 200), ('DM-0106: Exception', 423), ('', 200), ('', 200), ('', 200), ('', 200)]
        with mock.patch('dm.network.gateway.async_send_message', side_effect=side_effect) as mocked_send:
            r = self.i.lock(scope=Scope.ORCHESTRATION, servers=self.servers)
            self.assertIsInstance(r.failure(), ue.ErrorLock)
            self.assertEqual(1, len(r.failure().errors))
            self.assertIsInstance(r.failure().errors[0], ue.ErrorServerLock)
            self.assertEqual(self.s3, r.failure().errors[0].server)

        side_effect = [('', 200), ('', 200), (ne.TimeoutError(), None), ('', 200), ('', 200), ('', 200), ('', 200)]
        with mock.patch('dm.network.gateway.async_send_message', side_effect=side_effect) as mocked_send:
            r = self.i.lock(scope=Scope.ORCHESTRATION, servers=self.servers)
            self.assertIsInstance(r.failure(), ue.ErrorLock)
            self.assertEqual(1, len(r.failure().errors))
            self.assertIsInstance(r.failure().errors[0], ue.ErrorServerLock)
            self.assertEqual(self.s3, r.failure().errors[0].server)

        side_effect = [('', 200), ('', 200), ('', 200), ('', 200), (ne.TimeoutError(), None), ('', 200), ('', 200),
                       ('', 200), ('', 200), ('', 200), ('', 200)]
        with mock.patch('dm.network.gateway.async_send_message', side_effect=side_effect) as mocked_send:
            r = self.i.lock(scope=Scope.ORCHESTRATION, servers=self.servers)
            self.assertIsInstance(r.failure(), ue.ErrorLock)
            self.assertEqual(1, len(r.failure().errors))
            self.assertIsInstance(r.failure().errors[0], ue.ErrorServerLock)
            self.assertEqual(self.s1, r.failure().errors[0].server)
