from unittest import TestCase

from dimensigon.utils.var_context import VarContext, VariableNotFoundError


class TestVarContext(TestCase):

    def test_get(self):
        defaults = dict(d=4, o=4, s=4, v=4)
        variables = dict(v=1)
        vc = VarContext(defaults=defaults, variables=variables)

        self.assertEqual(4, vc.get('d'))

        with self.assertRaises(VariableNotFoundError):
            vc.get('x')
        self.assertIsNone(vc.get('x', None))
        self.assertEqual(2, vc.get('x', 2))

    def test_create_new_ctx(self):
        initials = dict(i=3, v=3)
        variables = dict(v=1)
        vc = VarContext(initials=initials, variables=variables)

        new_vs = vc.create_new_ctx(defaults=dict(i=2, d=2, v=2))

        self.assertEqual(1, new_vs.get('v'))
        self.assertEqual(3, new_vs.get('i'))
        self.assertEqual(2, new_vs.get('d'))

        vc.set('v', 4)
        self.assertEqual(4, new_vs.get('v'))

    def test_recursive(self):
        initials = dict(a='{{b}}')
        defaults = dict(b='{{c}}')
        variables = dict(c=1)
        vc = VarContext(initials=initials, defaults=defaults, variables=variables)

        self.assertEqual(1, vc.get('a'))

        vc.set('c', '{{a}}')
        with self.assertRaises(RecursionError):
            vc.get('a')

    def test_in(self):
        initials = dict(i=3)
        defaults = dict(d=2)
        variables = dict(v=1)
        vc = VarContext(initials=initials, defaults=defaults, variables=variables)

        self.assertIn('i', vc)
        self.assertIn('d', vc)
        self.assertIn('v', vc)

    def test_dict(self):
        initials = dict(i=3, v=3)
        defaults = dict(d=2, v=2)
        variables = dict(v=1)
        vc = VarContext(initials=initials, defaults=defaults, variables=variables)

        self.assertDictEqual(dict(i=3, d=2, v=1), dict(vc))
        self.assertEqual(3, len(vc))

    def test_empty(self):
        vc = VarContext()
        self.assertEqual(0, len(vc))
        self.assertEqual({}, dict(vc))
        with self.assertRaises(VariableNotFoundError):
            vc.get('x')

    def test_globals(self):
        globals = dict(g=4, d=4, i=4, v=4)
        defaults = dict(d=3, i=3, v=3)
        initials = dict(i=2, v=2)
        variables = dict(v=1)
        vc = VarContext(globals=globals, initials=initials, defaults=defaults, variables=variables)

        self.assertDictEqual(dict(d=3, i=2, v=1), dict(vc))
        self.assertEqual(3, len(vc))

        self.assertDictEqual(dict(g=4, i=4, d=4, v=4), dict(vc.globals))

