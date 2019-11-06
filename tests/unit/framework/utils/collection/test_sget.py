from unittest import TestCase

from dm.framework.utils.collection import sget


class TestSget(TestCase):

    def setUp(self) -> None:
        class AClass:
            attribute = {'foo': 'bar'}

        self.sentinel = AClass()
        self.dict_target = {
            'first_level': 'value',
            'second': {
                'level': 'value',
                'list': [{}, {'foo': 'list value'}],
                'non-list': {'1': {'foo': 'dict value'}},
            },
            1: 'int key',
            '1': 'string key',
            None: True,
            self.sentinel: 'sentinel value',
        }

    def test_simple_key(self):
        params = [('first_level', 'value'),
                  (1, 'int key'),
                  ('1', 'string key'),
                  (None, True),
                  (self.sentinel, 'sentinel value')]

        for key, result in params:
            with self.subTest():
                assert sget(self.dict_target, key) == result

    def test_key_structure(self):
        params = [
            ('second.level', 'value'),
            ('second.list.1.foo', 'list value'),
            ('second.non-list.1.foo', 'dict value'),
        ]
        for key, result in params:
            with self.subTest():
                assert sget(self.dict_target, key) == result

    def test_defaults(self):
        params = [
            ('second.level', 'not used', 'value'),
            ('second.non-existing', None, None),
            ('second.list.1.bar', 42, 42),
            ('second.non-list.17.foo', 42, 42),
        ]
        for key, default, result in params:
            with self.subTest():
                assert sget(self.dict_target, key, default) == result

    def test_list_default(self):
        assert sget([1, 2, 3], '17', 'default') == 'default'

    def test_attribute(self):
        params = [
            ('attribute', None, {'foo': 'bar'}),
            ('attribute.foo', None, 'bar'),
            ('attribute.baz', None, None),
            ('attribute.baz', 42, 42),
        ]
        for key, default, result in params:
            with self.subTest():
                assert sget(self.sentinel, key, default) == result


