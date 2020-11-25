import os
import sys

from prompt_toolkit.formatted_text import is_formatted_text


def get_raw_text(text):
    if is_formatted_text(text):
        return ''.join([token[1] for token in text.formatted_text])
    else:
        return text


def clean_none(data):
    return {k: v for k, v in data.items() if v is not None}


def is_interactive(output=False, error=False, heuristic=False):
    if not sys.stdin.isatty():
        return False
    if output and not sys.stdout.isatty():
        return False
    if error and not sys.stderr.isatty():
        return False

    if heuristic:
        home = os.getenv('HOME')
        homepath = os.getenv('HOMEPATH')
        if not homepath and (not home or home == '/'):
            return False
    return True
