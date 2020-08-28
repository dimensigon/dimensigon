import datetime as dt
from unittest import TestCase, mock

from dimensigon import defaults
from dimensigon.utils.cluster_manager import ClusterManager, _ClusterRegister, ClusterManagerCoordinator
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
        self.assertDictEqual({1: _ClusterRegister(1, now, None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, before_now)
        self.assertIsNotNone(self.cm.set_alive(1))
        self.assertDictEqual({1: _ClusterRegister(1, now, None)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, None)
        self.assertIsNone(self.cm.set_alive(1))
        self.assertDictEqual({1: _ClusterRegister(1, before_now, None)}, self.cm._cluster)

        self.assertIsNotNone(self.cm.set_alive(2))
        self.assertDictEqual({1: _ClusterRegister(1, before_now, None),
                              2: _ClusterRegister(2, now, None)}, self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_death(self, mock_now):
        mock_now.return_value = now

        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, now, now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, before_now)
        self.assertIsNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, before_now, before_now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, None)
        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, before_now, now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, after_now, None)
        self.assertIsNotNone(self.cm.set_death(1))
        self.assertDictEqual({1: _ClusterRegister(1, after_now, after_now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, after_now, None)
        self.assertIsNotNone(self.cm.set_death(1, before_now))
        self.assertDictEqual({1: _ClusterRegister(1, after_now, after_now)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, None)
        self.assertIsNotNone(self.cm.set_death(1, after_now))
        self.assertDictEqual({1: _ClusterRegister(1, before_now, after_now)}, self.cm._cluster)

    def test__update_cluster(self):
        self.cm._cluster = {1: _ClusterRegister(1, before_now, None),
                            2: _ClusterRegister(2, now, None),
                            3: _ClusterRegister(3, before_now, None),
                            4: _ClusterRegister(4, before_now, now),
                            5: _ClusterRegister(5, before_now, now),
                            6: _ClusterRegister(6, before_now, after_now),
                            7: _ClusterRegister(7, before_now, now),
                            8: _ClusterRegister(8, before_now, now),
                            10: _ClusterRegister(10, before_now, None)}

        self.cm._update_cluster([_ClusterRegister(1, now, None),
                                 _ClusterRegister(2, before_now, None),
                                 _ClusterRegister(3, before_now, now),
                                 _ClusterRegister(4, before_now, None),
                                 _ClusterRegister(5, before_now, after_now),
                                 _ClusterRegister(6, before_now, now),
                                 _ClusterRegister(7, after_now, None),
                                 _ClusterRegister(8, after_now, after_now),
                                 _ClusterRegister(9, before_now, None)])

        self.assertDictEqual({1: _ClusterRegister(1, before_now, None),
                              2: _ClusterRegister(2, before_now, None),
                              3: _ClusterRegister(3, before_now, now),
                              4: _ClusterRegister(4, before_now, now),
                              5: _ClusterRegister(5, before_now, now),
                              6: _ClusterRegister(6, before_now, now),
                              7: _ClusterRegister(7, after_now, None),
                              8: _ClusterRegister(8, after_now, after_now),
                              9: _ClusterRegister(9, before_now, None),
                              10: _ClusterRegister(10, before_now, None)}, self.cm._cluster)

    def test_get_cluster(self):
        self.cm._cluster[1] = _ClusterRegister(1, now, None)

        self.assertListEqual([dict(id=1, birth=str_now)], self.cm.get_cluster())

    def test_contains(self):
        self.cm._cluster[1] = _ClusterRegister(1, now, None)
        self.cm._cluster[2] = _ClusterRegister(2, now, now)

        self.assertTrue(1 in self.cm)
        self.assertTrue(2 not in self.cm)

    def test_iter(self):
        self.cm._cluster[1] = _ClusterRegister(1, now, None)
        self.cm._cluster[2] = _ClusterRegister(2, now, now)

        self.assertListEqual([1], [i for i in self.cm])

    def test_get_oldest_alive(self):
        self.cm._cluster = {1: _ClusterRegister(1, now, None),
                            2: _ClusterRegister(2, before_now, None)}

        self.assertEqual(2, self.cm.get_oldest_alive())


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
        self.assertDictEqual({1: _ClusterRegister(1, now, None, True)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, before_now)
        self.cm.set_alive(1)
        self.assertDictEqual({1: _ClusterRegister(1, now, None, True)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, None)
        self.cm.set_alive(1)
        self.assertDictEqual({1: _ClusterRegister(1, before_now, None, True)}, self.cm._cluster)

        self.cm.set_alive(2)
        self.assertDictEqual({1: _ClusterRegister(1, before_now, None, True),
                              2: _ClusterRegister(2, now, None, False)}, self.cm._cluster)

    @mock.patch('dimensigon.utils.cluster_manager.get_now')
    def test_set_death(self, mock_now):
        mock_now.return_value = now

        self.cm.set_death(1)
        self.assertDictEqual({1: _ClusterRegister(1, now, now, False)}, self.cm._cluster)

        self.cm._cluster[1] = _ClusterRegister(1, before_now, None, True)
        self.cm._cluster[2] = _ClusterRegister(2, now, None, False)
        self.cm._cluster[3] = _ClusterRegister(3, before_now, None, False)
        self.cm.set_death(1)
        self.assertDictEqual({1: _ClusterRegister(1, before_now, now, False),
                              2: _ClusterRegister(2, now, None, False),
                              3: _ClusterRegister(3, before_now, None, True)}, self.cm._cluster)

    def test__update_cluster(self):
        self.cm._cluster = {1: _ClusterRegister(1, before_now, None, True),
                            2: _ClusterRegister(2, now, None, True),
                            3: _ClusterRegister(3, before_now, None),
                            4: _ClusterRegister(4, before_now, now),
                            5: _ClusterRegister(5, before_now, now),
                            6: _ClusterRegister(6, before_now, after_now),
                            7: _ClusterRegister(7, before_now, now),
                            8: _ClusterRegister(8, before_now, now),
                            10: _ClusterRegister(10, before_now, None)}

        self.cm._update_cluster([_ClusterRegister(1, now, None),
                                 _ClusterRegister(2, before_now, None),
                                 _ClusterRegister(3, before_now, now),
                                 _ClusterRegister(4, before_now, None),
                                 _ClusterRegister(5, before_now, after_now),
                                 _ClusterRegister(6, before_now, now),
                                 _ClusterRegister(7, after_now, None, True),
                                 _ClusterRegister(8, after_now, after_now),
                                 _ClusterRegister(9, before_now, None)])

        self.assertDictEqual({1: _ClusterRegister(1, before_now, None, True),
                              2: _ClusterRegister(2, before_now, None),
                              3: _ClusterRegister(3, before_now, now),
                              4: _ClusterRegister(4, before_now, now),
                              5: _ClusterRegister(5, before_now, now),
                              6: _ClusterRegister(6, before_now, now),
                              7: _ClusterRegister(7, after_now, None),
                              8: _ClusterRegister(8, after_now, after_now),
                              9: _ClusterRegister(9, before_now, None),
                              10: _ClusterRegister(10, before_now, None)}, self.cm._cluster)


    def test_coordinators(self):
        self.cm._cluster = {1: _ClusterRegister(1, now, None, False),
                            2: _ClusterRegister(2, before_now, None, True),
                            3: _ClusterRegister(3, before_now, None, True)}

        self.assertListEqual([_ClusterRegister(2, before_now, None, True), _ClusterRegister(3, before_now, None, True)],
                             self.cm.coordinators)

    def test_get_older_coordinators(self):
        self.cm._cluster = {1: _ClusterRegister(1, now, None, False),
                            2: _ClusterRegister(2, after_now, None, True),
                            3: _ClusterRegister(3, before_now, None, True)}

        self.assertEqual(3, self.cm.get_oldest_coordinator())

    def test_set_coordinator(self):
        self.cm._cluster = {1: _ClusterRegister(1, now, None, False),
                            2: _ClusterRegister(2, after_now, None, True),
                            3: _ClusterRegister(3, before_now, None, True)}

        self.cm.set_coordinator(1)

        self.assertDictEqual({1: _ClusterRegister(1, now, None, True),
                              2: _ClusterRegister(2, after_now, None, False),
                              3: _ClusterRegister(3, before_now, None, False)}, self.cm._cluster)