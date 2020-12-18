import datetime as dt
import threading
from unittest import TestCase, mock

from dimensigon.domain.entities import Server

try:
    from unittest.mock import AsyncMock
except ImportError:
    from tests.base import AsyncMock

import dimensigon.web.network as ntwrk
from dimensigon import defaults
from dimensigon.use_cases.cluster import ClusterManager, NewEvent, DeathEvent, ZombieEvent, _Entry, AliveEvent
from dimensigon.web import db
from tests.base import OneNodeMixin

now = dt.datetime(2000, 1, 1, 0, 10, 0, tzinfo=dt.timezone.utc)


def handler(event, l, e):
    l.append(event)
    e.set()


class TestClusterManager(OneNodeMixin, TestCase):

    def setUp(self) -> None:
        super().setUp()

        self.new_event = threading.Event()
        self.mock_queue = mock.Mock()
        self.mock_dm = mock.Mock()
        self.mock_dm.flask_app = self.app
        self.mock_dm.engine = db.engine
        self.mock_dm.manager.dict.return_value = dict()
        self.mock_dm.server_id = self.s1.id

        self.cm = ClusterManager("Cluster", startup_event=threading.Event(), shutdown_event=threading.Event(),
                                 publish_q=self.mock_queue, event_q=None, dimensigon=self.mock_dm)

    def tearDown(self) -> None:
        self.cm._notify_cluster_out = mock.Mock()
        self.cm.shutdown()
        super().tearDown()

    def test_main_func(self):
        self.cm._send_data = mock.Mock(spec=self.cm._send_data)

        # New Event
        self.cm.put(1, keepalive=now)
        self.cm.main_func()

        self.cm.publish_q.safe_put.assert_called_once()
        self.assertIsInstance(self.mock_queue.safe_put.call_args[0][0], NewEvent)
        self.assertEqual(1, self.mock_queue.safe_put.call_args[0][0].args[0])
        self.assertEqual(_Entry(1, now, False, False), self.cm._registry.get(1))

        self.cm.zombie_threshold = dt.timedelta(seconds=0.05)
        now2 = now + dt.timedelta(minutes=1)

        self.mock_queue.reset_mock()
        # KeepAlive Event
        self.cm.put(1, now2)
        self.cm.main_func()
        self.cm.publish_q.safe_put.assert_not_called()
        self.assertEqual(_Entry(1, now2, False, False), self.cm._registry.get(1))

        self.mock_queue.reset_mock()
        # Zombie Event
        item = self.cm.queue.get(block=True)
        self.cm.queue.put(item)
        self.cm.main_func()
        self.cm.publish_q.safe_put.assert_called_once()
        self.assertIsInstance(self.mock_queue.safe_put.call_args[0][0], ZombieEvent)
        self.assertEqual(1, self.mock_queue.safe_put.call_args[0][0].args[0])
        self.assertEqual(_Entry(1, now2, False, True), self.cm._registry.get(1))

        self.cm.zombie_threshold = dt.timedelta(seconds=180)

        now3 = now2 + dt.timedelta(minutes=1)
        self.mock_queue.reset_mock()
        # Alive Event
        self.cm.put(1, keepalive=now3)
        self.cm.main_func()
        self.cm.publish_q.safe_put.assert_called_once()
        self.assertIsInstance(self.mock_queue.safe_put.call_args[0][0], AliveEvent)
        self.assertEqual(1, self.mock_queue.safe_put.call_args[0][0].args[0])
        self.assertEqual(_Entry(1, now3, False, False), self.cm._registry.get(1))

        now4 = now3 + dt.timedelta(minutes=2)
        self.mock_queue.reset_mock()
        # Death Event
        self.cm.put(1, now4, True)
        self.cm.main_func()
        self.cm.publish_q.safe_put.assert_called_once()
        self.assertIsInstance(self.mock_queue.safe_put.call_args[0][0], DeathEvent)
        self.assertEqual(1, self.mock_queue.safe_put.call_args[0][0].args[0])
        self.assertEqual(_Entry(1, now4, True, False), self.cm._registry.get(1))

    def test_get_alive(self):
        self.cm.put(1, now)
        self.cm.put(2, now)
        self.cm.put(3, now)
        for _ in range(3):
            self.cm.main_func()
        self.assertListEqual([1, 2, 3, self.s1.id], self.cm.get_alive())
        self.cm._registry[2].death = True
        self.cm._registry[3].zombie = True
        self.assertListEqual([1, self.s1.id], self.cm.get_alive())

    def test_get_zombies(self):
        self.cm.put(1, now)
        self.cm.main_func()
        self.assertListEqual([], self.cm.get_zombies())
        self.cm._registry[1].zombie = True
        self.assertListEqual([1], self.cm.get_zombies())

    @mock.patch('dimensigon.use_cases.cluster.get_now')
    def test_get_cluster(self, mock_get_now):
        mock_get_now.return_value = now
        self.cm.put(1, now)
        self.cm.put(2, now)
        self.cm.put(3, now)
        for _ in range(3):
            self.cm.main_func()
        self.assertListEqual([(1, now, False), (2, now, False), (3, now, False), (self.s1.id, now, False)],
                             self.cm.get_cluster())
        self.cm._registry[2].death = True
        self.cm._registry[3].zombie = True

        self.assertListEqual([(1, now, False), (2, now, True), (3, now, False), (self.s1.id, now, False)],
                             self.cm.get_cluster())

        self.assertListEqual([(1, now.strftime(defaults.DATETIME_FORMAT), False),
                              (2, now.strftime(defaults.DATETIME_FORMAT), True),
                              (3, now.strftime(defaults.DATETIME_FORMAT), False),
                              (self.s1.id, now.strftime(defaults.DATETIME_FORMAT), False)],
                             self.cm.get_cluster(str_format=defaults.DATETIME_FORMAT))

    def test___contains__(self):
        self.cm.put(1, now)
        self.cm.put(2, now)
        self.cm.put(3, now)
        for _ in range(3):
            self.cm.main_func()
        self.assertTrue(1 in self.cm)
        self.assertTrue(2 in self.cm)
        self.assertTrue(3 in self.cm)
        self.assertTrue(self.s1.id in self.cm)

        self.cm._registry[2].death = True
        self.cm._registry[3].zombie = True

        self.assertTrue(1 in self.cm)
        self.assertFalse(2 in self.cm)
        self.assertFalse(3 in self.cm)
        self.assertTrue(self.s1.id in self.cm)

    @mock.patch('dimensigon.use_cases.cluster.threading', )
    @mock.patch('dimensigon.use_cases.cluster.ntwrk.parallel_requests', spec=AsyncMock)
    @mock.patch('dimensigon.use_cases.cluster.Server.get_neighbours')
    @mock.patch('dimensigon.use_cases.cluster.get_root_auth')
    def test__send_data(self, mock_get_root_auth, mock_get_neighbours, mock_parallel_requests, mock_threading):
        async def parallel_responses(responses):
            return responses

        mock_get_neighbours.return_value = [self.s1]
        mock_get_root_auth.return_value = 'auth'
        mock_parallel_requests.return_value = parallel_responses([ntwrk.Response(code=200, server=self.s1)])

        self.cm.put(1, now)
        self.cm.put(2, now, death=True)
        for _ in range(2):
            self.cm.main_func()

        self.cm._send_data()

        self.assertEqual(0, len(self.cm._buffer))
        mock_parallel_requests.assert_called_once_with(mock_get_neighbours.return_value, 'POST',
                                                       view_or_url='api_1_0.cluster',
                                                       json=[dict(id=1, death=False,
                                                                  keepalive=now.strftime(defaults.DATEMARK_FORMAT)),
                                                             dict(id=2, death=True,
                                                                  keepalive=now.strftime(defaults.DATEMARK_FORMAT)),
                                                             ], auth=mock_get_root_auth.return_value, securizer=False
                                                       )

        with self.subTest("Error sending data"):
            async def parallel_responses(responses):
                raise Exception()

            self.assertEqual(0, len(self.cm._buffer))
            mock_parallel_requests.return_value = parallel_responses(None)
            self.cm.put(1, now + dt.timedelta(minutes=1))
            self.cm.put(2, now + dt.timedelta(minutes=1), death=True)
            for _ in range(2):
                self.cm.main_func()

            self.assertIsNotNone(self.cm._buffer)

            self.cm._send_data()

            self.assertIsNotNone(self.cm._buffer)

    @mock.patch('dimensigon.use_cases.cluster.get_now')
    @mock.patch('dimensigon.use_cases.cluster.ntwrk.post')
    @mock.patch('dimensigon.use_cases.cluster.get_root_auth')
    def test__notify_cluster_in(self, mock_get_root_auth, mock_post, mock_get_now):
        mock_get_root_auth.return_value = 'auth'
        mock_post.side_effect = [ntwrk.Response(code=200, msg={
            'cluster': [(1, now.strftime(defaults.DATEMARK_FORMAT), False),
                        (2, now.strftime(defaults.DATEMARK_FORMAT), False)],
            'neighbours': [1, 2]})]
        mock_get_now.return_value = now

        s2 = Server('node2', port=5000)
        s2.set_route(None, gate=s2.gates[0], cost=0)

        db.session.add(s2)
        self.cm._route_initiated = mock.Mock()
        self.cm._notify_cluster_in()
        self.cm.main_func()
        self.assertDictEqual({1: _Entry(id=1, keepalive=now, death=False),
                              2: _Entry(id=2, keepalive=now, death=False)},
                             self.cm._registry)

        routes = [s2.route.to_json()]
        mock_post.assert_called_once_with(s2, 'api_1_0.cluster_in', view_data=dict(server_id=str(self.s1.id)),
                                          json=dict(keepalive=now.strftime(defaults.DATEMARK_FORMAT), routes=routes)
                                          , timeout=10, auth='auth')

    @mock.patch('dimensigon.use_cases.cluster.get_now')
    @mock.patch('dimensigon.use_cases.cluster.ntwrk.parallel_requests', spec=AsyncMock)
    @mock.patch('dimensigon.use_cases.cluster.Server.get_neighbours')
    @mock.patch('dimensigon.use_cases.cluster.get_root_auth')
    def test__notify_cluster_out(self, mock_get_root_auth, mock_get_neighbours, mock_parallel_requests, mock_get_now):
        async def parallel_responses(responses):
            return responses

        mock_get_root_auth.return_value = 'auth'
        mock_get_neighbours.return_value = [self.s1]

        with self.subTest("Successful cluster out message"):
            mock_parallel_requests.return_value = parallel_responses([ntwrk.Response(code=200)])
            mock_get_now.return_value = now

            self.cm._notify_cluster_out()

            mock_parallel_requests.assert_called_once_with([self.s1], 'post',
                                                           view_or_url='api_1_0.cluster_out',
                                                           view_data=dict(server_id=str(self.s1.id)),
                                                           json={'death': now.strftime(defaults.DATEMARK_FORMAT)},
                                                           timeout=2, auth='auth')

        with self.subTest("Error sending cluster out message"):
            mock_get_neighbours.return_value = [self.s1]
            mock_parallel_requests.reset_mock()
            mock_parallel_requests.return_value = parallel_responses([ntwrk.Response(code=500, server=self.s1)])
            self.cm.logger.warning = mock.Mock()
            self.cm._notify_cluster_out()
            self.cm.logger.warning.assert_called_once_with(
                f"Unable to send data to {self.s1}: {ntwrk.Response(code=500, server=self.s1)}")

        with self.subTest("No servers to send message"):
            mock_get_neighbours.return_value = []
            mock_parallel_requests.reset_mock()
            self.cm._notify_cluster_out()
            mock_parallel_requests.assert_not_called()
