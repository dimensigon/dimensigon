import argparse
from unittest import TestCase

from dimensigon.dshell.argparse_raise import create_parser, GuessArgumentParser


class TestArgparseRaise(TestCase):
    def test_create_parser(self):
        def status(args):
            pass

        def server_list(args):
            pass

        data = {
            'status': [{'argument': 'node', 'completer': None}, status],
            'server': {
                'list': [{'argument': '--json', 'action': 'store_true', 'required': False},
                         [{'argument': '--like'},
                          {'argument': '--name', 'completer': None},
                          {'argument': '--id'},
                          {'argument': '--last', 'action': 'store', 'type': int}],
                         server_list
                         ],

            }}

        parser = create_parser(data)
        # namespace = parser.parse_args('status node1'.split())
        # self.assertEqual(status, namespace.func)
        # self.assertEqual('node1', namespace.node)

        namespace = parser.parse_args('server list --j'.split())
        self.assertEqual(server_list, namespace.func)
        self.assertEqual('node1', namespace.name)
        self.assertEqual(True, namespace.json)

        namespace = parser.parse_args('server list --json --name node1'.split())
        self.assertEqual(server_list, namespace.func)
        self.assertEqual('node1', namespace.name)
        self.assertEqual(True, namespace.json)

        with self.assertRaises(argparse.ArgumentError):
            parser.parse_args('server list --name node1 --id 1'.split())


class TestGuessArgparse(TestCase):
    def test_create_parser(self):
        def status(args):
            pass

        def server_list(args):
            pass

        data = {
            'status': [{'argument': 'node', 'completer': None}, status],
            'server': {
                'list': [{'argument': '--json', 'action': 'store_true', 'required': False},
                         [{'argument': '--like'},
                          {'argument': '--name', 'completer': None},
                          {'argument': '--id'},
                          {'argument': '--last', 'action': 'store', 'type': int}],
                         server_list
                         ],

            }}

        parser = create_parser(data, GuessArgumentParser())

        namespace = parser.parse_args('server list --json --name node1 --data aa'.split())
        args = dict(namespace._get_kwargs())

        self.assertNotIn('--data', args)

        namespace = parser.parse_args('server list --json --name node1 --last x'.split())
        args = dict(namespace._get_kwargs())
        self.assertEqual('x', namespace.last)

        namespace = parser.parse_args('server list --j'.split())
        self.assertFalseIn(namespace.json)

    def test_parameters(self):
        data = {
            'status': [{'argument': 'arg1', 'completer': None, 'nargs': 2},
                       {'argument': 'arg2', 'completer': None}],
        }

        parser = create_parser(data, GuessArgumentParser())

        namespace = parser.parse_args('status first'.split())
        args = dict(namespace._get_kwargs())
        self.assertDictEqual({'arg1': ['first'], 'arg2': None}, args)