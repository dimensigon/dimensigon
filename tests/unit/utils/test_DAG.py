from unittest import TestCase

from dm.utils.dag import DAG, DAGError


class TestDAG(TestCase):
    def test_nodes(self):
        G = DAG()
        self.assertListEqual(G.nodes, [])

    def test_pred(self):
        G = DAG()
        self.assertDictEqual(G.pred, {})

    def test_succ(self):
        g = DAG()
        self.assertDictEqual(g.succ, {})

    def test_add_node(self):
        g = DAG()
        g.add_node(1)
        self.assertListEqual(g.nodes, [1])

        class Foo():
            pass

        bar = Foo()
        g.add_node(bar)

        self.assertListEqual(g.nodes, [1, bar])

    def test_add_nodes_from(self):
        g = DAG()
        g.add_nodes_from(range(3))
        self.assertListEqual(g.nodes, [0, 1, 2])

    def test_add_edge(self):
        class Foo():
            pass

        g = DAG()
        g.add_edge(2, 3)
        bar = Foo()
        g.add_edge(3, bar)
        g.add_edge(3, bar)
        self.assertListEqual(g.nodes, [2, 3, bar])

        self.assertDictEqual(g.succ, {2: [3], 3: [bar], bar: []})

    def test_add_edges_from(self):
        class Foo():
            pass

        bar = Foo()
        g = DAG()
        g.add_edges_from([(3, bar), (2, 3), (2, 3)])

        self.assertDictEqual(g.succ, {2: [3], 3: [bar], bar: []})

    def test_remove_node(self):
        class Foo():
            pass

        bar = Foo()
        g = DAG()
        g.add_edges_from([(3, bar), (2, 3), (2, 3)])

        with self.assertRaises(DAGError):
            g.remove_node(5)

        g.remove_node(3)

        self.assertListEqual(g.nodes, [bar, 2])

        self.assertDictEqual(g.succ, {2: [], bar: []})
        self.assertDictEqual(g.pred, {2: [], bar: []})

    def test_remove_nodes_from(self):
        class Foo():
            pass

        bar = Foo()
        g = DAG()
        g.add_edges_from([(3, bar), (2, 3), (2, 3)])

        g.remove_nodes_from([5, 2, bar])

        self.assertListEqual(g.nodes, [3])

        self.assertDictEqual(g.succ, {3: []})
        self.assertDictEqual(g.pred, {3: []})

    def test_remove_edge(self):
        class Foo():
            pass

        bar = Foo()
        g = DAG()
        g.add_edges_from([(3, bar), (2, 3), (2, 3)])

        g.remove_edge(2, 3)

        self.assertListEqual(g.succ[2], [])

    def test_remove_edges_from(self):
        class Foo():
            pass

        bar = Foo()
        g = DAG()
        g.add_edges_from([(3, bar), (2, 3), (2, 3)])
        ebunch = [(1, 2), (2, 3)]
        g.remove_edges_from(ebunch)

        self.assertListEqual(g.succ[2], [])

    def test_level(self):
        g = DAG([(1, 2), (1, 7), (7, 2), (2, 4), (2, 3), (4, 5), (4, 6)])

        self.assertEqual(g.level(1), 1)
        self.assertEqual(g.level(2), 3)
        self.assertEqual(g.level(3), 4)
        self.assertEqual(g.level(4), 4)
        self.assertEqual(g.level(5), 5)
        self.assertEqual(g.level(6), 5)
        self.assertEqual(g.level(7), 2)

    def test_get_nodes_at_level(self):
        g = DAG([(1, 2), (1, 7), (7, 2), (2, 4), (2, 3), (4, 5), (4, 6)])

        self.assertListEqual([4, 3], g.get_nodes_at_level(4))

    def test_depth(self):
        g = DAG([(1, 2), (1, 7), (7, 2), (2, 4), (2, 3), (4, 5), (4, 6)])

        self.assertEqual(5, g.depth)

    def test_is_cyclic(self):
        g = DAG([(2, 0), (2, 3), (0, 1), (0, 2)])
        self.assertTrue(g.is_cyclic())

        g = DAG([(2, 0), (2, 3), (0, 1), (1, 2)])
        self.assertTrue(g.is_cyclic())

        g = DAG([(2, 0), (2, 3), (0, 1), (3, 3)])
        self.assertTrue(g.is_cyclic())

        g = DAG([(2, 0), (2, 3), (0, 1), (4, 5), (5, 4)])
        self.assertTrue(g.is_cyclic())

    def test_to_dict_of_lists(self):
        g = DAG([(1, 2), (2, 3), (2, 4)])
        self.assertDictEqual(g.to_dict_of_lists(), {1: [2], 2: [3, 4], 3: [], 4: []})

    def test_from_dict_of_lists(self):
        g = DAG.from_dict_of_lists({1: [2], 2: [3, 4], 3: [], 4: [], 5: []})
        self.assertDictEqual(g.pred, {1: [], 2: [1], 3: [2], 4: [2], 5: []})

    def test_root(self):
        g = DAG.from_dict_of_lists({1: [2], 2: [3, 4], 3: [], 4: [], 5: []})
        self.assertListEqual(g.root, [1, 5])

    def test_copy(self):
        g1 = DAG.from_dict_of_lists({1: [2], 2: [3, 4], 3: [], 4: [], 5: []})
        g2 = g1.copy()
        g2.add_edges_from([(2, 5), (2, 6)])

        self.assertDictEqual(g1.succ, {1: [2], 2: [3, 4], 3: [], 4: [], 5: []})
        self.assertDictEqual(g1.pred, {1: [], 2: [1], 3: [2], 4: [2], 5: []})
        self.assertListEqual(g1.nodes, [1, 2, 3, 4, 5])

        self.assertDictEqual(g2.succ, {1: [2], 2: [3, 4, 5, 6], 3: [], 4: [], 5: [], 6: []})
        self.assertDictEqual(g2.pred, {1: [], 2: [1], 3: [2], 4: [2], 5: [2], 6: [2]})
        self.assertListEqual(g2.nodes, [1, 2, 3, 4, 5, 6])

    def test_subtree(self):
        g = DAG([(1, 2), (1, 7), (7, 2), (2, 4), (2, 3), (4, 5), (4, 6)])

        self.assertDictEqual(g.subtree([2]), {2: [4, 3], 3: [], 4: [5, 6], 5: [], 6: []})
        self.assertDictEqual(g.subtree([2, 7]), {7: [2], 2: [4, 3], 3: [], 4: [5, 6], 5: [], 6: []})
        self.assertDictEqual(g.subtree([5, 6]), {5: [], 6: []})
