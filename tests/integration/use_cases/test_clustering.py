import datetime as dt
import threading
import time
from functools import partial
from unittest import TestCase, mock

from dimensigon.use_cases.clustering import ClusterManager, NewEvent, DeathEvent, ZombieEvent, AliveEvent, _Entry, \
    KeepAliveEvent

now = dt.datetime(1, 1, 1, 0, 10, 0)


def handler(event, l, e):
    l.append(event)
    e.set()


class TestClusterManager(TestCase):

    def setUp(self) -> None:
        self.new = []
        self.keepalive = []
        self.zombie = []
        self.death = []
        self.alive = []

        self.new_event = threading.Event()
        self.keepalive_event = threading.Event()
        self.zombie_event = threading.Event()
        self.death_event = threading.Event()
        self.alive_event = threading.Event()

        self.cm = ClusterManager(None, None, zombie_threshold=180, delayed=180)
        self.cm.start()

    def tearDown(self) -> None:
        self.cm.stop()

    def test_cluster_manager(self):
        self.cm._send_data = mock.Mock(spec=self.cm._send_data)
        self.cm.listen(NewEvent, partial(handler, l=self.new, e=self.new_event))
        self.cm.listen(KeepAliveEvent, partial(handler, l=self.keepalive, e=self.keepalive_event))
        self.cm.listen(ZombieEvent, partial(handler, l=self.zombie, e=self.zombie_event))
        self.cm.listen(DeathEvent, partial(handler, l=self.death, e=self.death_event))
        self.cm.listen(AliveEvent, partial(handler, l=self.alive, e=self.alive_event))

        # New Event
        self.cm.put((1, now, False))
        self.new_event.wait(10)

        self.assertListEqual([NewEvent(1)], self.new)
        self.assertListEqual([], self.keepalive)
        self.assertListEqual([], self.zombie)
        self.assertListEqual([], self.death)
        self.assertListEqual([], self.alive)
        self.assertEqual(_Entry(1, now, False, False), self.cm._registry.get(1))

        self.cm.zombie_threshold = dt.timedelta(seconds=0.5)
        after_now = now + dt.timedelta(minutes=1)
        # KeepAlive Event
        self.cm.put((1, after_now, False))

        self.keepalive_event.wait(10)
        self.assertListEqual([NewEvent(1)], self.new)
        self.assertListEqual([KeepAliveEvent(1, after_now)], self.keepalive)
        self.assertListEqual([], self.zombie)
        self.assertListEqual([], self.death)
        self.assertListEqual([], self.alive)
        self.assertEqual(_Entry(1, after_now, False, False), self.cm._registry.get(1))

        self.assertListEqual([NewEvent(1)], self.new)
        self.assertListEqual([KeepAliveEvent(1, after_now)], self.keepalive)
        start = time.time()
        while len(self.zombie) == 0 and time.time() - start < 5:
            time.sleep(0.2)
        self.assertListEqual([ZombieEvent(1)], self.zombie)
        self.assertListEqual([], self.death)
        self.assertListEqual([], self.alive)
        self.assertEqual(_Entry(1, after_now, False, True), self.cm._registry.get(1))

        self.cm.zombie_threshold = dt.timedelta(seconds=180)
        after_now2 = now + dt.timedelta(minutes=2)
        # Death Event
        self.cm.put((1, after_now2, True))

        self.death_event.wait(10)
        self.assertListEqual([NewEvent(1)], self.new)
        self.assertListEqual([KeepAliveEvent(1, after_now)], self.keepalive)
        self.assertListEqual([ZombieEvent(1)], self.zombie)
        self.assertListEqual([DeathEvent(1)], self.death)
        self.assertListEqual([], self.alive)
        self.assertEqual(_Entry(1, after_now2, True, False), self.cm._registry.get(1))
