from unittest import TestCase, mock

from prompt_toolkit.completion import CompleteEvent, WordCompleter
from prompt_toolkit.document import Document

from dm.dshell.completer import ResourceCompleter, DshellCompleter
from dm.web.network import Response


class TestResourceCompleter(TestCase):
    default_response = Response(msg=[
        {
            "last_modified_at": "20200616.113822.505932+0200",
            "id": "00000000-1111-0000-0000-000000000000",
            "name": "dev1",
            "granules": []
        },
        {
            "last_modified_at": "20200616.113955.580271+0200",
            "id": "00000000-2222-0000-0000-000000000000",
            "name": "dev2",
            "granules": []
        },
        {
            "last_modified_at": "20200616.113955.580271+0200",
            "id": "00000000-3333-0000-0000-000000000000",
            "name": "node3",
            "granules": []
        }
    ], code=200)

    @mock.patch('dm.dshell.completer.request')
    def test_get_completions(self, mock_request):
        mock_request.return_value = self.default_response

        completer = ResourceCompleter('servers', 'name')
        # Static list on empty input.
        completions = completer.get_completions(Document(""), CompleteEvent())
        self.assertListEqual(["dev1", "dev2", "node3"], [c.text for c in completions])

        completions = completer.get_completions(Document("d"), CompleteEvent())
        self.assertListEqual(["dev1", "dev2"], [c.text for c in completions])

    @mock.patch('dm.dshell.completer.request')
    def test_filter(self, mock_request):
        mock_request.return_value = self.default_response

        completer = ResourceCompleter('servers', 'name', match_middle=True)

        completions = completer.get_completions(Document("3"), CompleteEvent())
        self.assertListEqual(["node3"], [c.text for c in completions])

        completer = ResourceCompleter('servers', 'name', ignore_case=True)

        completions = completer.get_completions(Document("D"), CompleteEvent())
        self.assertListEqual(["dev1", "dev2"], [c.text for c in completions])


class TestDshellCompleter(TestCase):

    @mock.patch('dm.dshell.completer.request')
    def test_get_completions(self, mock_request):
        mock_request.return_value = Response(msg=[
            {
                "last_modified_at": "20200616.113822.505932+0200",
                "id": "01",
                "name": "dev1",
                "granules": []
            },
            {
                "last_modified_at": "20200616.113955.580271+0200",
                "id": "02",
                "name": "dev2",
                "granules": []
            },
            {
                "last_modified_at": "20200616.113955.580271+0200",
                "id": "13",
                "name": "node3",
                "granules": []
            }
        ], code=200)

        data = {
            'status': [{'argument': 'node', 'completer': ResourceCompleter('servers', 'name')}],
            'server': {
                'list': [{'argument': '--json', 'action': 'store_true', 'required': False},
                         [{'argument': '--like'},
                          {'argument': '--name', 'completer': ResourceCompleter('servers', 'name')},
                          {'argument': '--id', 'completer': ResourceCompleter('servers', 'id')},
                          {'argument': '--last', 'action': 'store', 'type': int}]
                         ],
                'show': [{'argument': '--json', 'action': 'store_true', 'required': False},
                         {'argument': 'node', 'completer': ResourceCompleter('servers', 'name')}]},
            'nargs': [{'argument': 'compiler', 'completer': WordCompleter(['python', 'ruby', 'c++']), 'nargs': 2},
                      {'argument': 'so', 'completer': WordCompleter(['windows', 'linux', 'mac'])},
                      {'argument': '--foo', 'nargs': '?', 'completer': WordCompleter(['aaa', 'bbb'])},
                      {'argument': '--bar', 'nargs': '*', 'completer': WordCompleter(['x1', 'x2', 'x3'])}]
        }

        completer = DshellCompleter.from_nested_dict(data)
        # Static list on empty input.
        completions = completer.get_completions(Document(""), CompleteEvent())
        self.assertListEqual(["status", "server", "nargs"], [c.text for c in completions])

        # mid word
        completions = completer.get_completions(Document("st"), CompleteEvent())
        self.assertListEqual(["status"], [c.text for c in completions])

        # completed word
        completions = completer.get_completions(Document("status"), CompleteEvent())
        self.assertListEqual([], [c.text for c in completions])

        completions = completer.get_completions(Document("status "), CompleteEvent())
        self.assertListEqual(["dev1", "dev2", "node3"], [c.text for c in completions])

        completions = completer.get_completions(Document("server "), CompleteEvent())
        self.assertListEqual(["list", "show"], [c.text for c in completions])

        completions = completer.get_completions(Document("server l"), CompleteEvent())
        self.assertListEqual(["list"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list "), CompleteEvent())
        self.assertListEqual(["--json", "--like", "--name", "--id", "--last"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list --j"), CompleteEvent())
        self.assertListEqual(["--json"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list --json "), CompleteEvent())
        self.assertListEqual(["--json", "--like", "--name", "--id", "--last"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list --json --id "), CompleteEvent())
        self.assertListEqual(["01", "02", "13"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list --json --id 0"), CompleteEvent())
        self.assertListEqual(["01", "02"], [c.text for c in completions])

        completions = completer.get_completions(Document("server list --json --id 01 "), CompleteEvent())
        self.assertListEqual(["--json", "--like", "--name", "--id", "--last"], [c.text for c in completions])

        completions = completer.get_completions(Document("server show "), CompleteEvent())
        self.assertListEqual(["--json", "dev1", "dev2", "node3"], [c.text for c in completions])

        completions = completer.get_completions(Document("nargs "), CompleteEvent())
        self.assertListEqual(['--foo', '--bar', 'python', 'ruby', 'c++'], [c.text for c in completions])

        completions = completer.get_completions(Document("nargs --foo "), CompleteEvent())
        self.assertListEqual(['aaa', 'bbb', '--foo', '--bar', 'python', 'ruby', 'c++'], [c.text for c in completions])

        completions = completer.get_completions(Document("nargs --foo s "), CompleteEvent())
        self.assertListEqual(['--foo', '--bar', 'python', 'ruby', 'c++'], [c.text for c in completions])

        completions = completer.get_completions(Document("nargs --bar "), CompleteEvent())
        self.assertListEqual(['x1', 'x2', 'x3', '--foo', '--bar', 'python', 'ruby', 'c++'],
                             [c.text for c in completions])

        completions = completer.get_completions(Document("nargs --bar x"), CompleteEvent())
        self.assertListEqual(['x1', 'x2', 'x3'], [c.text for c in completions])

        completions = completer.get_completions(Document("nargs --bar x1 "), CompleteEvent())
        self.assertListEqual(['x1', 'x2', 'x3', '--foo', '--bar', 'python', 'ruby', 'c++'],
                             [c.text for c in completions])
