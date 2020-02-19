from unittest import TestCase


class TestLocker(TestCase):

    def test_locker(self):
        from dm.domain.locker import Locker, PreventingLockState, UnlockState, LockState, StateError, ApplicantError
        locker = Locker().set_timeout(0.001)
        applicant = 1
        locker.preventing_lock(applicant)

        self.assertIsInstance(locker._state, PreventingLockState)

        with self.assertRaises(StateError):
            locker.preventing_lock(applicant)

        with self.assertRaises(ApplicantError):
            locker.preventing_lock(2)

        # wait timer to be executed
        try:
            while not locker._state.timer.finished.is_set():
                pass
        except AttributeError:
            pass

        self.assertIsInstance(locker._state, UnlockState)

        locker.preventing_lock(applicant=applicant)
        locker.lock(applicant=applicant)

        self.assertIsInstance(locker._state, LockState)

        with self.assertRaises(StateError):
            locker.preventing_lock(applicant)

        with self.assertRaises(StateError):
            locker.lock(applicant)

        with self.assertRaises(ApplicantError):
            locker.preventing_lock(2)

        locker.unlock(applicant)

        self.assertIsInstance(locker._state, UnlockState)

        with self.assertRaises(StateError):
            locker.unlock(applicant)

        with self.assertRaises(StateError):
            locker.lock(applicant)

        locker.set_timeout(10)

        locker.preventing_lock(applicant=2)
        locker.lock(applicant=2)

        self.assertIsInstance(locker._state, LockState)
