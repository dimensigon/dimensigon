from unittest import TestCase

import rsa

from dm.utils.helpers import convert


class TestConvert(TestCase):
    def test_convert(self):
        d = {'param1': 'value1', 'param2': {'test': 'test_value', 'subparam1': {'level3': 3}}}

        o = convert(d)
        self.assertEqual(o.param2.subparam1.level3, 3)

        self.assertDictEqual(o.param2.subparam1, {'level3': 3})