import datetime as dt
from unittest import TestCase, mock

from dimensigon import defaults
from dimensigon.utils.cluster_manager import ClusterManager, _ClusterRegister, ClusterManagerCoordinator, \
    _ClusterRegisterSession, ClusterManagerSession
from dimensigon.utils.helpers import get_now

now = get_now()
str_now = now.strftime(defaults.DATEMARK_FORMAT)

before_now = now - dt.timedelta(seconds=1)
after_now = now + dt.timedelta(seconds=1)


class TestClusterManager(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cm = ClusterManager()
        cls.maxDiff = None

    def setUp(self) -> None:
        self.cm.clear_cluster()

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_alive(self, mock_now):
        mock_now.return_value = now

        self.assertIsNotNone(self.cm.set_alive(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=before_now)
        self.assertIsNotNone(self.cm.set_alive(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=None)
        self.assertIsNone(self.cm.set_alive(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=None)}, self.cm._cluster)

        self.assertIsNotNone(self.cm.set_alive(2))
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=None),
                              2: _ClusterRegister(2, birth=now, keepalive=now, death=None)}, self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_death(self, mock_now):
        mock_now.return_value = now

        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, death=now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, keepalive=before_now, death=before_now)
        self.assertIsNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=before_now, death=before_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, keepalive=before_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=before_now, death=now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=after_now, keepalive=after_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, birth=after_now, keepalive=after_now, death=after_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=after_now, keepalive=after_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, before_now))
        self.assertDictEqual({1: _ClusterRegister(1, birth=after_now, keepalive=after_now, death=after_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, keepalive=before_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, after_now))
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=before_now, death=after_now)},
                             self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_keepalive(self, mock_now):
        mock_now.return_value = now

        self.cm.set_keepalive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=before_now)
        self.cm.set_keepalive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=None)
        self.cm.set_keepalive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm.set_keepalive(2)
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=now, death=None),
                              2: _ClusterRegister(2, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

    def test__update_cluster(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=before_now, keepalive=before_now, death=None),
                            2: _ClusterRegister(2, birth=now, keepalive=now, death=None),
                            3: _ClusterRegister(3, birth=before_now, keepalive=before_now, death=None),
                            4: _ClusterRegister(4, birth=before_now, keepalive=before_now, death=now),
                            5: _ClusterRegister(5, birth=before_now, keepalive=before_now, death=now),
                            6: _ClusterRegister(6, birth=before_now, keepalive=before_now, death=after_now),
                            7: _ClusterRegister(7, birth=before_now, keepalive=before_now, death=now),
                            8: _ClusterRegister(8, birth=before_now, keepalive=before_now, death=now),
                            10: _ClusterRegister(10, birth=before_now, keepalive=before_now, death=None)}

        self.cm._update_cluster([_ClusterRegister(1, birth=now, keepalive=now, death=None),
                                 _ClusterRegister(2, birth=before_now, keepalive=before_now, death=None),
                                 _ClusterRegister(3, birth=before_now, keepalive=before_now, death=now),
                                 _ClusterRegister(4, birth=before_now, keepalive=before_now, death=None),
                                 _ClusterRegister(5, birth=before_now, keepalive=before_now, death=after_now),
                                 _ClusterRegister(6, birth=before_now, keepalive=before_now, death=now),
                                 _ClusterRegister(7, birth=after_now, keepalive=after_now, death=None),
                                 _ClusterRegister(8, birth=after_now, keepalive=after_now, death=after_now),
                                 _ClusterRegister(9, birth=before_now, keepalive=before_now, death=None)])

        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, keepalive=now, death=None),
                          2: _ClusterRegister(2, birth=before_now, keepalive=now, death=None),
                          3: _ClusterRegister(3, birth=before_now, keepalive=before_now, death=now),
                          4: _ClusterRegister(4, birth=before_now, keepalive=before_now, death=now),
                          5: _ClusterRegister(5, birth=before_now, keepalive=before_now, death=now),
                          6: _ClusterRegister(6, birth=before_now, keepalive=before_now, death=now),
                          7: _ClusterRegister(7, birth=after_now, keepalive=after_now, death=None),
                          8: _ClusterRegister(8, birth=after_now, keepalive=after_now, death=after_now),
                          9: _ClusterRegister(9, birth=before_now, keepalive=before_now, death=None),
                          10: _ClusterRegister(10, birth=before_now, keepalive=before_now, death=None)},
                         self.cm._cluster)

    def test_get_cluster(self):
        self.cm._cluster[1] = _ClusterRegister(1, birth=now, death=None)

        self.assertListEqual([dict(id=1, birth=str_now)], self.cm.get_cluster())

    def test_contains(self):
        self.cm._cluster[1] = _ClusterRegister(1, birth=now, death=None)
        self.cm._cluster[2] = _ClusterRegister(2, birth=now, death=now)

        self.assertTrue(1 in self.cm)
        self.assertTrue(2 not in self.cm)

    def test_iter(self):
        self.cm._cluster[1] = _ClusterRegister(1, birth=now, death=None)
        self.cm._cluster[2] = _ClusterRegister(2, birth=now, death=now)

        self.assertListEqual([1], [i for i in self.cm])

    def test_get_oldest_alive(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=now, death=None),
                            2: _ClusterRegister(2, birth=before_now, death=None)}

        self.assertEqual(2, self.cm.get_oldest_alive())

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_get_delta_keepalive(self, mock_now):
        mock_now.return_value = after_now
        self.cm._cluster = {1: _ClusterRegister(1, birth=now, keepalive=now, death=None),
                            2: _ClusterRegister(2, birth=after_now, keepalive=after_now, death=None)}

        self.assertListEqual([], self.cm.get_delta_keepalive(dt.timedelta(seconds=0)))
        self.assertListEqual([2], self.cm.get_delta_keepalive(dt.timedelta(seconds=1)))
        self.assertListEqual([1, 2], self.cm.get_delta_keepalive(dt.timedelta(seconds=2)))


class TestClusterManagerCoordinator(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cm = ClusterManagerCoordinator()
        cls.maxDiff = None

    def setUp(self) -> None:
        self.cm.clear_cluster()

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_alive(self, mock_now):
        mock_now.return_value = now

        self.cm.set_alive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None, coordinator=True)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=before_now)
        self.cm.set_alive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, keepalive=now, death=None, coordinator=True)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=None)
        self.cm.set_alive(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=None, coordinator=True)}, self.cm._cluster)

        self.cm.set_alive(2)
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=None, coordinator=True),
                              2: _ClusterRegister(2, birth=now, keepalive=now, death=None, coordinator=False)}, self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_death(self, mock_now):
        mock_now.return_value = now

        self.cm.set_death(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=now, death=now, coordinator=False)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, birth=before_now, death=None, coordinator=True)
        self.cm._cluster[2] = _ClusterRegister(2, birth=now, death=None, coordinator=False)
        self.cm._cluster[3] = _ClusterRegister(3, birth=before_now, death=None, coordinator=False)
        self.cm.set_death(1)
        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=now, coordinator=False),
                              2: _ClusterRegister(2, birth=now, death=None, coordinator=False),
                              3: _ClusterRegister(3, birth=before_now, death=None, coordinator=True)}, self.cm._cluster)


    def test__update_cluster(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=before_now, death=None, coordinator=True),
                            2: _ClusterRegister(2, birth=now, death=None, coordinator=True),
                            3: _ClusterRegister(3, birth=before_now, death=None),
                            4: _ClusterRegister(4, birth=before_now, death=now),
                            5: _ClusterRegister(5, birth=before_now, death=now),
                            6: _ClusterRegister(6, birth=before_now, death=after_now),
                            7: _ClusterRegister(7, birth=before_now, death=now),
                            8: _ClusterRegister(8, birth=before_now, death=now),
                            10: _ClusterRegister(10, birth=before_now, death=None)}

        self.cm._update_cluster([_ClusterRegister(1, birth=now, death=None),
                                 _ClusterRegister(2, birth=before_now, death=None),
                                 _ClusterRegister(3, birth=before_now, death=now),
                                 _ClusterRegister(4, birth=before_now, death=None),
                                 _ClusterRegister(5, birth=before_now, death=after_now),
                                 _ClusterRegister(6, birth=before_now, death=now),
                                 _ClusterRegister(7, birth=after_now, death=None, coordinator=True),
                                 _ClusterRegister(8, birth=after_now, death=after_now),
                                 _ClusterRegister(9, birth=before_now, death=None)])

        self.assertDictEqual({1: _ClusterRegister(1, birth=before_now, death=None, coordinator=True),
                              2: _ClusterRegister(2, birth=before_now, death=None),
                              3: _ClusterRegister(3, birth=before_now, death=now),
                              4: _ClusterRegister(4, birth=before_now, death=now),
                              5: _ClusterRegister(5, birth=before_now, death=now),
                              6: _ClusterRegister(6, birth=before_now, death=now),
                              7: _ClusterRegister(7, birth=after_now, death=None),
                              8: _ClusterRegister(8, birth=after_now, death=after_now),
                              9: _ClusterRegister(9, birth=before_now, death=None),
                              10: _ClusterRegister(10, birth=before_now, death=None)}, self.cm._cluster)

    def test_coordinators(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=now, death=None, coordinator=False),
                            2: _ClusterRegister(2, birth=before_now, death=None, coordinator=True),
                            3: _ClusterRegister(3, birth=before_now, death=None, coordinator=True)}

        self.assertListEqual([_ClusterRegister(2, birth=before_now, death=None, coordinator=True),
                              _ClusterRegister(3, birth=before_now, death=None, coordinator=True)],
                             self.cm.coordinators)

    def test_get_older_coordinators(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=now, death=None, coordinator=False),
                            2: _ClusterRegister(2, birth=after_now, death=None, coordinator=True),
                            3: _ClusterRegister(3, birth=before_now, death=None, coordinator=True)}

        self.assertEqual(3, self.cm.get_oldest_coordinator())

    def test_set_coordinator(self):
        self.cm._cluster = {1: _ClusterRegister(1, birth=now, death=None, coordinator=False),
                            2: _ClusterRegister(2, birth=after_now, death=None, coordinator=True),
                            3: _ClusterRegister(3, birth=before_now, death=None, coordinator=True)}

        self.cm.set_coordinator(1)

        self.assertDictEqual({1: _ClusterRegister(1, birth=now, death=None, coordinator=True),
                              2: _ClusterRegister(2, birth=after_now, death=None, coordinator=False),
                              3: _ClusterRegister(3, birth=before_now, death=None, coordinator=False)},
                             self.cm._cluster)


class TestClusterManagerSession(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cm = ClusterManagerSession()
        cls.maxDiff = None

    def setUp(self) -> None:
        self.cm.clear_cluster()

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_alive(self, mock_now):
        mock_now.return_value = now

        self.assertIsNotNone(self.cm.set_alive(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, death=before_now)
        self.assertIsNotNone(self.cm.set_alive(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, death=None)
        self.assertIsNone(self.cm.set_alive(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, death=None)}, self.cm._cluster)

        self.assertIsNotNone(self.cm.set_alive(2, 21))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, death=None),
                              2: _ClusterRegisterSession(2, session=21, birth=now, keepalive=now, death=None)}, self.cm._cluster)

        self.assertIsNotNone(self.cm.set_alive(1, 12))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=12, birth=now, keepalive=now, death=None),
                              2: _ClusterRegisterSession(2, session=21, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_death(self, mock_now):
        mock_now.return_value = now

        self.assertIsNotNone(self.cm.set_death(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=now, death=now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=before_now)
        self.assertIsNone(self.cm.set_death(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=before_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=after_now, keepalive=after_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, 11))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=after_now, keepalive=after_now, death=after_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=after_now, keepalive=after_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, 11, before_now))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=after_now, keepalive=after_now, death=after_now)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=None)
        self.assertIsNotNone(self.cm.set_death(1, 11, after_now))
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=before_now, death=after_now)},
                             self.cm._cluster)

        with self.assertRaises(ValueError):
            self.cm.set_death(1, 12, after_now)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_keepalive(self, mock_now):
        mock_now.return_value = now

        self.cm.set_keepalive(1, 11)
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, death=before_now)
        self.cm.set_keepalive(1, 11)
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=now, death=None)},
                             self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegisterSession(1, session=11, birth=before_now, death=None)
        self.cm.set_keepalive(1, 11)
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=now, death=None)}, self.cm._cluster)

        self.cm.set_keepalive(2, 21)
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=now, death=None),
                              2: _ClusterRegisterSession(2, session=21, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

        self.cm.set_keepalive(2, 22)
        self.assertDictEqual({1: _ClusterRegisterSession(1, session=11, birth=before_now, keepalive=now, death=None),
                              2: _ClusterRegisterSession(2, session=22, birth=now, keepalive=now, death=None)},
                             self.cm._cluster)

    def test__update_cluster(self):
        self.cm._cluster = {1: _ClusterRegisterSession(1, birth=before_now, keepalive=before_now, death=None),
                            2: _ClusterRegisterSession(2, birth=now, keepalive=now, death=None),
                            3: _ClusterRegisterSession(3, birth=before_now, keepalive=before_now, death=None),
                            4: _ClusterRegisterSession(4, birth=before_now, keepalive=before_now, death=now),
                            5: _ClusterRegisterSession(5, birth=before_now, keepalive=before_now, death=now),
                            6: _ClusterRegisterSession(6, birth=before_now, keepalive=before_now, death=after_now),
                            7: _ClusterRegisterSession(7, birth=before_now, keepalive=before_now, death=now),
                            8: _ClusterRegisterSession(8, birth=before_now, keepalive=before_now, death=now),
                            10: _ClusterRegisterSession(10, birth=before_now, keepalive=before_now, death=None)}

        self.cm._update_cluster([_ClusterRegisterSession(1, birth=now, keepalive=now, death=None),
                                 _ClusterRegisterSession(2, birth=before_now, keepalive=before_now, death=None),
                                 _ClusterRegisterSession(3, birth=before_now, keepalive=before_now, death=now),
                                 _ClusterRegisterSession(4, birth=before_now, keepalive=before_now, death=None),
                                 _ClusterRegisterSession(5, birth=before_now, keepalive=before_now, death=after_now),
                                 _ClusterRegisterSession(6, birth=before_now, keepalive=before_now, death=now),
                                 _ClusterRegisterSession(7, birth=after_now, keepalive=after_now, death=None),
                                 _ClusterRegisterSession(8, birth=after_now, keepalive=after_now, death=after_now),
                                 _ClusterRegisterSession(9, birth=before_now, keepalive=before_now, death=None)])

        self.assertDictEqual({1: _ClusterRegisterSession(1, birth=before_now, keepalive=now, death=None),
                          2: _ClusterRegisterSession(2, birth=before_now, keepalive=now, death=None),
                          3: _ClusterRegisterSession(3, birth=before_now, keepalive=before_now, death=now),
                          4: _ClusterRegisterSession(4, birth=before_now, keepalive=before_now, death=now),
                          5: _ClusterRegisterSession(5, birth=before_now, keepalive=before_now, death=now),
                          6: _ClusterRegisterSession(6, birth=before_now, keepalive=before_now, death=now),
                          7: _ClusterRegisterSession(7, birth=after_now, keepalive=after_now, death=None),
                          8: _ClusterRegisterSession(8, birth=after_now, keepalive=after_now, death=after_now),
                          9: _ClusterRegisterSession(9, birth=before_now, keepalive=before_now, death=None),
                          10: _ClusterRegisterSession(10, birth=before_now, keepalive=before_now, death=None)},
                         self.cm._cluster)