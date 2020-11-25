import json
import logging
from pprint import pprint

import pygments
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import PygmentsTokens
from pygments.lexers.web import JSONLexer

from dimensigon.dshell import environ as env
from dimensigon.utils.helpers import format_exception
from dimensigon.web.network import Response

logger = logging.getLogger('dshell')


def dprint(msg):
    if isinstance(msg, str):
        if msg not in ('\n', None, ''):
            print(msg)
    elif isinstance(msg, Response):
        if msg.code:
            dprint(msg.msg)
        else:
            dprint(msg.exception)
    elif isinstance(msg, Exception):
        if env.get('DEBUG'):
            dprint(format_exception(msg))
        else:
            dprint(str(msg) if str(msg) else msg.__class__.__name__)
    else:
        try:
            tokens = list(pygments.lex(json.dumps(msg, indent=2), lexer=JSONLexer()))
        except:
            pprint(msg)
        else:
            print_formatted_text(PygmentsTokens(tokens), end="")
