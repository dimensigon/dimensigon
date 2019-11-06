from unittest import TestCase

from dm.domain.locker import PriorityLocker, PriorityError, LockState


class TestPriorityLocker(TestCase):

    def test_priorityLocker(self):
        pl1 = PriorityLocker(priority=1)
        pl2 = PriorityLocker(priority=2)

        lockers = {1: pl1, 2: pl2}

        pl1.preventing_lock(lockers, 1)

        with self.assertRaises(PriorityError):
            pl2.preventing_lock(lockers, 2)

        pl1.lock(1)

        with self.assertRaises(PriorityError):
            pl2.preventing_lock(lockers, 2)

        pl1.unlock(1)
        pl2.preventing_lock(lockers, 1)
        pl1.preventing_lock(lockers, 1)
        pl2.lock(1)
        pl1.lock(1)

        self.assertIsInstance(pl2.state, LockState)
