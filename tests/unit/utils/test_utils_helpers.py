from unittest import TestCase

from dimensigon.utils.helpers import convert, get_distributed_entities


class TestConvert(TestCase):

    def test_convert(self):
        d = {'param1': 'value1', 'param2': {'test': 'test_value', 'subparam1': {'level3': 3}}}

        o = convert(d)
        self.assertEqual(o.param2.subparam1.level3, 3)

        self.assertDictEqual(o.param2.subparam1, {'level3': 3})


    def test_get_distributed_entities(self):
        import dimensigon.domain.entities
        entities = get_distributed_entities()

        for name, cls in entities:
            self.assertTrue(hasattr(cls, 'last_modified_at'))
            self.assertTrue(name in dimensigon.domain.entities.__all__)
