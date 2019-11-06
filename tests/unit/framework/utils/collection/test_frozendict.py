import operator
from copy import copy
from unittest import TestCase

from dm.framework.utils.collection import frozendict, freeze


class TestFrozendict(TestCase):

    @staticmethod
    def test_freeze():
        collection = {
            '1': 1,
            'list': [2, 3, 4],
            'tuple': (5, 6),
            'set': {7, 8},
            'dict': {
                '7': 9,
                '8': (10, 11),
            },
            (1, 2): 'an iterable key',
            frozendict(some='value'): 'a structured key',
        }
        assert freeze(collection) == frozendict({
            '1': 1,
            'list': (2, 3, 4),
            'tuple': (5, 6),
            'set': frozenset({8, 7}),
            'dict': frozendict({
                '7': 9,
                '8': (10, 11)
            }),
            (1, 2): 'an iterable key',
            frozendict({'some': 'value'}): 'a structured key'
        })

    def test_immutability(self):
        params = [
            lambda d: operator.setitem(d, 'key', 'value'),
            lambda d: operator.delitem(d, 'key'),
            frozendict.clear,
            frozendict.popitem,
            lambda d: frozendict.pop(d, 'key', None),
            lambda d: frozendict.setdefault(d, 'key', 'value'),
            lambda d: frozendict.update(d, key='value'),
        ]
        for mutator in params:
            with self.assertRaises(AttributeError):
                mutator(frozendict())

    def test_copying(self):
        value = frozendict(a=1)
        copied = copy(value)
        assert value == copied
        assert value is not copied
