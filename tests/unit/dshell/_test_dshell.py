# If the given text doesn't end with a newline, the interface won't finish.
from unittest import TestCase

from commands import nested_dict
from completer import DshellCompleter
from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput


class TestCompleter(TestCase):

    def test_completer(self):
        text = 'server \t\r'

        inp = create_pipe_input()

        try:
            inp.send_text(text)
            session = PromptSession(
                input=inp,
                output=DummyOutput(),
                editing_mode=EditingMode.VI,
                completer=DshellCompleter.from_nested_dict(nested_dict)
            )

            result = session.prompt()
        finally:
            inp.close()