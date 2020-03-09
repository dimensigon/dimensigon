import datetime
from dataclasses import dataclass
from unittest import TestCase, mock

# function to mock the time
from dm.use_cases.mediator import SessionManager, SessionExpired


def mocked_get_now(**kwargs):
    return datetime.datetime(2012, 1, 1, 10, 10, 10) + datetime.timedelta(**kwargs)


@dataclass
class Carrier:
    session: int = None


class TestSessionManager(TestCase):
    def test_session_manager_context(self):
        SessionManager.clear_session_pool()
        with mock.patch('dm.use_cases.mediator.get_now', side_effect=mocked_get_now):
            c1 = Carrier()
            with SessionManager(c1) as session:
                session.var1 = 5
                session.msg = c1
                c1.session = session.id

            c2 = Carrier()
            with SessionManager(c2) as session:
                session.var1 = 1
                session.msg = c2
                c2.session = session.id

            with SessionManager(c2) as session:
                self.assertEqual(1, session.var1)
                self.assertEqual(c2, session.msg)

            self.assertEqual(len(SessionManager._session_pool), 2)

        with mock.patch('dm.use_cases.mediator.get_now', side_effect=lambda: mocked_get_now(hours=2)):
            with self.assertRaises(SessionExpired):
                with SessionManager(c1):
                    pass

            self.assertEqual(len(SessionManager._session_pool), 1)
