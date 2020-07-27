"""
Utility function and classes for dimensigon

"""
import copy
import typing as t


class DAGError(Exception):
    """Base Class Exception in DAG"""


T = t.TypeVar('T')
Tree = t.Dict[T, t.List[T]]


class DAG(t.Generic[T]):
    """
    Base class for directed graphs.
    A DAG stores nodes and edges
    DAG hold directed edges.  Self loops are allowed but multiple
    (parallel) edges are not.
    Nodes can be arbitrary (hashable) Python objects.
    By convention `None` is not used as a node.
    Edges are represented as links between nodes.
    ----------
    Create an empty graph structure (a "null graph") with no nodes and
    no edges.
    >>> G = DAG()
    G can be grown in several ways.
    **Nodes:**
    Add one node at a time:
    >>> G.add_node(1)
    Add the nodes from any container (a list, dict, set or
    even the lines from a file or the nodes from another graph).
    >>> G.add_nodes_from([2, 3])
    >>> G.add_nodes_from(range(100, 110))
    >>> H = DAG([(2,3),(3,4)])
    >>> G.add_nodes_from(H)
    In addition to strings and integers any hashable Python object
    (except None) can represent a node, e.g. a customized node object,
    or even another Graph.
    >>> G.add_node(H)
    **Edges:**
    G can also be grown by adding edges.
    Add one edge,
    >>> G.add_edge(1, 2)
    a list of edges,
    >>> G.add_edges_from([(1, 2), (1, 3)])
    or a collection of edges,
    >>> G.add_edges_from(H.edges)
    If some edges connect nodes not yet in the graph, the nodes
    are added automatically.  There are no errors when adding
    nodes or edges that already exist.
    Many common graph features allow python syntax to speed reporting.
    >>> 1 in G     # check if node in graph
    True
    >>> [n for n in G if n < 3]  # iterate through nodes
    [1, 2]
    >>> len(G)  # number of nodes in graph
    5

    """

    def __init__(self, edges_for_adding: t.List[t.Tuple[T, T]] = None):
        self._nodes = []
        self._pred = {}
        self._succ = {}
        if edges_for_adding:
            self.add_edges_from(edges_for_adding)

    @property
    def nodes(self) -> t.List[T]:
        return self._nodes

    @property
    def ordered_nodes(self) -> t.List[T]:
        nodes = []
        for l in range(1, self.depth + 1):
            nodes.extend(self.get_nodes_at_level(l))
        return nodes

    @property
    def pred(self) -> t.Dict[T, t.List[T]]:
        return self._pred

    @property
    def succ(self) -> t.Dict[T, t.List[T]]:
        return self._succ

    @property
    def root(self) -> t.List[T]:
        return [k for k, v in self._pred.items() if len(v) == 0]

    def __iter__(self) -> t.Iterator[T]:
        """Iterate over the nodes. Use: 'for n in G'.
        Returns
        -------
        niter : iterator
            An iterator over all nodes in the graph.
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> [n for n in G]
        [0, 1, 2, 3]
        >>> list(G)
        [0, 1, 2, 3]
        """
        return iter(self._nodes)

    def __contains__(self, n) -> bool:
        """Returns True if n is a node, False otherwise. Use: 'n in G'.
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> 1 in G
        True
        """
        try:
            return n in self._nodes
        except TypeError:
            return False

    def __len__(self) -> int:
        """Returns the number of nodes. Use: 'len(G)'.
        Returns
        -------
        nodes:
            The number of nodes in the graph.
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> len(G)
        4
        """
        return len(self._nodes)

    def __getitem__(self, n: T) -> t.List[T]:
        """Returns a dict of neighbors of node n.  Use: 'G[n]'.
        Parameters
        ----------
        n:
           A node in the graph.
        Returns
        -------
        adj_list:
           The successor list for nodes connected to n.
        Notes
        -----
        G[n] is the same as G.adj[n] and similar to G.neighbors(n)
        (which is an iterator over G.adj[n])
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> G[1]
        [2]
        """
        return self._succ[n]

    def add_node(self, node_for_adding: T) -> 'DAG':
        """Returns the graph with the added node
        Parameters
        ----------
        node_for_adding : node
           A node in the graph.
        Returns
        -------
        graph : DAG
          The graph with the node added
        Examples
        --------
        >>> G = DAG()
        >>> G.add_node(1)
        >>> G.nodes
        [1]
        """
        if node_for_adding not in self._nodes:
            self._succ[node_for_adding] = []
            self._pred[node_for_adding] = []
            self._nodes.append(node_for_adding)

    def add_nodes_from(self, nodes_for_adding: t.List[T]):
        for n in nodes_for_adding:
            self.add_node(n)

    def remove_node(self, n: T) -> None:
        """Remove node n.
        Removes the node n and all adjacent edges.
        Attempting to remove a non-existent node will raise an exception.
        Parameters
        ----------
        n:
           A node in the graph
        Raises
        -------
        NetworkXError
           If n is not in the graph.
        See Also
        --------
        remove_nodes_from
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> list(G.edges)
        [(1, 2), (2, 3), (3, 4)]
        >>> G.remove_node(2)
        >>> G.edges
        [(3, 4)]
        """
        try:
            nbrs = self._succ[n]

        except KeyError:  # NetworkXError if n not in self
            raise DAGError("The node %s is not in the digraph." % (n,))
        for u in nbrs:
            self._pred[u].remove(n)
        for u in self._pred[n]:
            self._succ[u].remove(n)  # remove all edges n-u in digraph
        self._nodes.remove(n)
        del self._pred[n]
        del self._succ[n]

    def remove_nodes_from(self, nodes: t.Iterable[T]):
        """Remove multiple nodes.
        Parameters
        ----------
        nodes : iterable container
            A container of nodes (list, dict, set, etc.).  If a node
            in the container is not in the graph it is silently ignored.
        See Also
        --------
        remove_node
        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> e = list(G.nodes)
        >>> e
        [0, 1, 2]
        >>> G.remove_nodes_from(e)
        >>> list(G.nodes)
        []
        """
        for n in nodes:
            try:
                self.remove_node(n)
            except DAGError:
                pass  # silent failure on remove

    def add_edge(self, u_of_edge, v_of_edge):
        """Add an edge between u and v.

        The nodes u and v will be automatically added if they are
        not already in the graph.

        Edge attributes can be specified with keywords or by directly
        accessing the edge's attribute dictionary. See examples below.

        Parameters
        ----------
        u, v : nodes
           Nodes can be, for example, strings or numbers.
           Nodes must be hashable (and not None) Python objects.

        See Also
        --------
        add_edges_from : add a collection of edges

        Notes
        -----
        Adding an edge that already exists doesn't do anything.

        Examples
        --------
        The following all add the edge e=(1, 2) to graph G:
        >>> G = DAG()
        >>> e = (1, 2)
        >>> G.add_edge(1, 2)           # explicit two-node form
        >>> G.add_edge(*e)             # single edge as tuple of two nodes
        >>> G.add_edges_from( [(1, 2)] ) # add edges from iterable container
        """

        u, v = u_of_edge, v_of_edge
        # add nodes
        if not u in self._nodes:
            self._nodes.append(u)
            self._succ[u] = []
            self._pred[u] = []
        if not v in self._nodes:
            self._nodes.append(v)
            self._succ[v] = []
            self._pred[v] = []
        if v not in self._succ[u]:
            self._succ[u].append(v)
            self._pred[v].append(u)

    def add_edges_from(self, ebunch_to_add):
        """Add all the edges in ebunch_to_add.

        Parameters
        ----------
        ebunch_to_add : container of edges
            Each edge given in the container will be added to the
            graph. The edges must be given as 2-tuples (u, v).


        See Also
        --------
        add_edge : add a single edge

        Notes
        -----
        Adding the same edge twice has no effect.

        Examples
        --------
        >>> G = DAG()
        >>> G.add_edges_from([(0, 1), (1, 2)]) # using a list of edge tuples
        >>> e = zip(range(0, 3), range(1, 4))
        >>> G.add_edges_from(e) # Add the path graph 0-1-2-3
        """
        for e in ebunch_to_add:
            ne = len(e)
            if ne == 2:
                u, v = e
            else:
                raise DAGError(
                    "Edge tuple %s must be a 2-tuple" % (e,))
            self.add_edge(u, v)

    def remove_edge(self, u, v):
        """Remove the edge between u and v.

        Parameters
        ----------
        u, v : nodes
            Remove the edge between nodes u and v.

        Raises
        ------
        DAGError
            If there is not an edge between u and v.

        See Also
        --------
        remove_edges_from : remove a collection of edges

        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> G.remove_edge(2, 3)
        >>> e = (1, 2)
        >>> G.remove_edge(*e) # unpacks e from an edge tuple
        """
        try:
            self._succ[u].remove(v)
            self._pred[v].remove(u)
        except KeyError:
            raise DAGError("The edge %s-%s not in graph." % (u, v))

    def remove_edges_from(self, ebunch):
        """Remove all edges specified in ebunch.

        Parameters
        ----------
        ebunch: list or container of edge tuples
            Each edge given in the list or container will be removed
            from the graph. The edges must be  2-tuples (u, v) edge between u and v.

        See Also
        --------
        remove_edge : remove a single edge

        Notes
        -----
        Will fail silently if an edge in ebunch is not in the graph.

        Examples
        --------
        >>> G = DAG([(1,2),(2,3),(3,4)])
        >>> ebunch = [(1, 2), (2, 3)]
        >>> G.remove_edges_from(ebunch)
        """
        for e in ebunch:
            u, v = e[:2]  # ignore edge data
            if u in self._succ and v in self._succ[u]:
                self._succ[u].remove(v)
                self._pred[v].remove(u)

    def level(self, node):
        """The level of a node is one greater than the level of its parent.
        The level of the root node is 1.

        Parameters
        ----------
        node: Any
            node from which we want to get it's level

        Examples
        --------
        >>> G = DAG([('a','b'),('b','c'),('c','d')])
        >>> G.level('c')
        3
        >>> G.add_edges_from([('a','e'), ('e','b')]
        >>> G.level('c')
        4

        Returns
        -------
        int:
            level of corresponding node
        """
        if len(self._pred[node]) == 0:
            return 1
        else:
            levels = [self.level(s) for s in self._pred[node]]
            if levels:
                return max(levels) + 1
            else:
                return 1

    # def get_nodes_at_level(self, level, step=None, nodes=None, visited_nodes=None):
    #     """Returns a list with a nodes at level
    #
    #      Parameters
    #     ----------
    #     level: level from which you want to get the nodes
    #
    #     Examples
    #     --------
    #     >>> G = DAG([('a','b'),('b','c'),('c','d')])
    #     >>> G.get_nodes_at_level(3)
    #     ['c']
    #     >>> G.add_edges_from([('b','e')]
    #     >>> G.get_nodes_at_level(3)
    #     ['c', 'e']
    #     """
    #     nodes = nodes or []
    #     visited_nodes = visited_nodes or []
    #
    #     if step == None:
    #         if self.root_step.height == height:
    #             nodes.append(self.root_step)
    #             return nodes
    #         else:
    #             for s in self.root_step.child_do_steps:
    #                 if not s in visited_nodes:
    #                     self._get_steps_at_height(height, s, nodes, visited_nodes)
    #                     visited_nodes.append(s)
    #             return nodes
    #     else:
    #         if step.height == height:
    #             nodes.append(step)
    #         elif step.height > height:
    #             for s in step.child_do_steps:
    #                 if not s in visited_nodes:
    #                     self._get_steps_at_height(height, s, nodes, visited_nodes)
    #                     visited_nodes.append(s)

    def _is_cyclic_util(self, v, visited, rec_stack):
        """Depth First Traversal can be used to detect a cycle in a Graph.
        DFS for a connected graph produces a tree. There is a cycle in a graph only if there is
        a back edge present in the graph. A back edge is an edge that is from a node to
        itself (self-loop) or one of its ancestor in the tree produced by DFS.

        To detect a back edge, we can keep track of vertices currently in recursion stack of
        function for DFS traversal. If we reach a vertex that is already in the recursion stack,
        then there is a cycle in the tree. The edge that connects current vertex to the vertex in
        the recursion stack is a back edge. We have used recStack[] array to keep track of vertices
        in the recursion stack.

        Parameters
        ----------
        v: vertex to make the DFS
        visited: dict with all nodes. A nodes visited has true inside
        rec_stack: to keep track of vertices in the recursion stack

        Reference
        ---------
        https://www.geeksforgeeks.org/detect-cycle-in-a-graph/
        """

        # Mark current node as visited and
        # adds to recursion stack
        visited[v] = True
        rec_stack[v] = True

        # Recur for all neighbours
        # if any neighbour is visited and in
        # recStack then graph is cyclic
        for neighbour in self._succ[v]:
            if not visited[neighbour]:
                if self._is_cyclic_util(neighbour, visited, rec_stack):
                    return True
            elif rec_stack[neighbour]:
                return True

        # The node needs to be poped from
        # recursion stack before function ends
        rec_stack[v] = False
        return False

    # Returns true if graph is cyclic else false
    def is_cyclic(self):
        """
        Given a directed graph, check whether the graph contains a cycle or not.
        Function returns true if the given graph contains at least one cycle, else returns false

        Return
        ------
        boolean

        """
        visited = {n: False for n in self._nodes}
        rec_stack = {n: False for n in self._nodes}
        for node in self._nodes:
            if visited[node] == False:
                if self._is_cyclic_util(node, visited, rec_stack):
                    return True
        return False

    def to_dict_of_lists(self):
        """Converts the tree into a dict of lists containing every node and its successors

        Examples
        --------
        >>> G = DAG([(1, 2),(2, 3),(2, 4)])
        >>> G.to_dict_of_lists()
        {1:[2], 2: [3, 4], 3: [], 4:[]}
        """

        return self._succ

    @classmethod
    def from_dict_of_lists(cls, dtree):
        g = cls()
        g.add_nodes_from((n for n in dtree))

        for k, v in dtree.items():
            for n in v:
                g.add_edge(k, n)

        return g

    def get_nodes_at_level(self, level):
        """

        Parameters
        ----------
        level

        Returns
        -------

        """
        return [n for n in self if self.level(n) == level]

    @property
    def depth(self):
        return max([self.level(n) for n in self])

    def copy(self) -> 'DAG':
        """
        Makes a copy of the current DAG. All the node objects remain the same. We make a copy of the graph dependency

        Returns
        -------
        dag:
            graph copied
        """
        g = DAG()
        g._nodes = copy.copy(self._nodes)
        g._succ = {k: copy.copy(v) for k, v in self._succ.items()}
        g._pred = {k: copy.copy(v) for k, v in self._pred.items()}
        return g

    def _fill_subtree(self, node: T, subtree: Tree):
        for n in self.succ[node]:
            if n not in subtree:
                self._fill_subtree(n, subtree)
        subtree.update({node: self.succ[node]})

    def subtree(self, starts_with: t.Union[t.Iterable[T], t.List[T]]) -> Tree:
        st = {}
        for n in starts_with:
            if n not in st:
                self._fill_subtree(n, st)
        return st
