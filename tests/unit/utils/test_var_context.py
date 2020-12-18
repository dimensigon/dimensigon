import pickle
from unittest import TestCase

from dimensigon.utils.var_context import Context


class TestContext(TestCase):

    def test_server_key_ctx(self):
        c = Context({'foo': 'bar'})

        local_vars = {}

        c1 = c.local_ctx(local_vars, 1)
        cc1 = c.local_ctx(local_vars, 1)
        c2 = c.local_ctx(local_vars, 2)
        self.assertEqual(id(cc1.input.maps[0]), id(c1._server_variables[1]))
        self.assertEqual(id(c2.input.maps[0]), id(c1._server_variables[2]))
        self.assertEqual(id(c2._server_variables[1]), id(c1._server_variables[1]))
        self.assertEqual(id(c2._server_variables[2]), id(c1._server_variables[2]))
        self.assertEqual(id(c2._server_variables[1]), id(cc1._server_variables[1]))
        self.assertEqual(id(c2._server_variables[2]), id(cc1._server_variables[2]))

        c2.set('new_var', 'new_value')

        self.assertDictEqual({1: {}, 2: {'new_var': 'new_value'}}, dict(c._server_variables))
        self.assertDictEqual({'foo': 'bar'}, dict(c.input))

        c1.set('new_var', 'new_value')
        self.assertDictEqual({1: {}, 2: {}}, dict(c._server_variables))

        self.assertDictEqual({'foo': 'bar', 'new_var': 'new_value'}, dict(c.input))

        c1['new_var'] = 'new_value2'
        self.assertDictEqual({1: {'new_var': 'new_value2'}, 2: {}}, dict(c._server_variables))

        c2['new_var'] = 'new_value2'
        self.assertDictEqual({1: {}, 2: {}}, dict(c._server_variables))

        self.assertDictEqual({'foo': 'bar', 'new_var': 'new_value2'}, dict(c.input))

        c1.set('file', 'node1')
        c2.set('file', 'node2')

        with self.assertRaises(KeyError):
            c['file']

        c1.set('common_file', 'common')
        c2.set('common_file', 'common')
        self.assertEqual('common', c['common_file'])

    def test_pickle(self):
        c = Context({'foo': 'bar'}, {'global': 'g'}, {'local': 'l'}, key_server_ctx=1, server_variables={'server': 's'},
                    vault={'vault': 'v'})

        dumped_c = pickle.dumps(c)

        loaded_c = pickle.loads(dumped_c)

        self.assertDictEqual(c.__dict__, loaded_c.__dict__)
