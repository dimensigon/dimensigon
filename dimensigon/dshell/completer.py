import logging
import shlex
import typing as t
from typing import Iterable

from prompt_toolkit import HTML
from prompt_toolkit.completion import Completer, CompleteEvent, Completion, WordCompleter
from prompt_toolkit.completion.nested import NestedDict
from prompt_toolkit.document import Document

import dimensigon.dshell.network as ntwrk
from dimensigon.dshell.argparse_raise import GuessArgumentParser, create_parser, DictAction
from dimensigon.dshell.catalog import fuzzy_match, get_catalog
from dimensigon.dshell.output import dprint
from dimensigon.dshell.utils import get_raw_text
from dimensigon.utils.helpers import is_iterable_not_string


class DshellWordCompleter(WordCompleter):
    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        # Get list of words.
        words = self.words
        if callable(words):
            words = words()

        # Get word/text before cursor.
        if self.sentence:
            word_before_cursor = document.text_before_cursor
        else:
            word_before_cursor = document.get_word_before_cursor(
                WORD=True, pattern=self.pattern
            )

        if self.ignore_case:
            word_before_cursor = word_before_cursor.lower()

        def word_matches(word: str, meta_data=None) -> bool:
            """ True when the word before the cursor matches. """
            if self.ignore_case:
                word = word.lower()
            raw = get_raw_text(meta_data)
            if self.match_middle:
                return (word_before_cursor in word and word_before_cursor != word) \
                       or raw is not None and word_before_cursor in raw
            else:
                return (word.startswith(
                    word_before_cursor) and word_before_cursor != word) or raw is not None and raw.startswith(
                    word_before_cursor)

        for a in words:
            display_meta = self.meta_dict.get(a, None)
            if word_matches(a, display_meta):
                if " " in a:
                    aa = a.replace("\"", '\\"')
                    yield Completion(f'"{aa}"', display=a, display_meta=display_meta)
                else:
                    yield Completion(a, -len(word_before_cursor), display_meta=display_meta)


class ResourceCompleter(Completer):

    def __init__(self, resource, key='id', meta_key=None, meta_html_format=None, ignore_case: bool = False,
                 match_middle: bool = True,
                 filters: t.List[t.Union[str, t.Tuple[str, str]]] = None,
                 transforms: t.Dict[str, t.Callable[[t.Any], t.Any]] = None,
                 resource_params: t.Dict['str', 'str'] = None) -> None:
        self.resource_params = resource_params or {}
        self.transforms = transforms
        self.match_middle = match_middle
        self.ignore_case = ignore_case
        self.resource = resource
        self.key = key
        self.meta_format = meta_html_format
        self.meta_key = meta_key
        self.filters = []
        for f in filters or []:
            if isinstance(f, str):
                self.filters.append((f, f.replace('-', '')))
            else:
                self.filters.append(f)

    def get_completions(self, document: Document, complete_event: CompleteEvent, var_filters: dict = None) -> \
            Iterable[Completion]:
        url_filters = {}
        for filter in self.filters:
            source, dest = filter
            if var_filters:
                value = var_filters.get(dest, None)
                if value:
                    if is_iterable_not_string(value):
                        value = ','.join(value)
                    url_filters.update({f'filter[{dest}]': value})

        try:
            url = ntwrk.generate_url(self.resource, {**url_filters, **self.resource_params})
        except:
            return
        res = ntwrk.request('get', url, login=False, timeout=3)
        if res.code == 200:
            words = []
            meta_words = {}
            for e in res.msg:
                if isinstance(e, dict) and e.get(self.key) not in words:
                    words.append(e.get(self.key))
                    if self.meta_key or self.meta_format:
                        if self.meta_format:
                            if self.transforms:
                                for key, transform in self.transforms.items():
                                    if key in e:
                                        val = e.get(key)
                                        try:
                                            e['key'] = transform(val)
                                        except:
                                            pass
                            try:
                                format = self.meta_format.format(**e)
                            except:
                                pass
                            else:
                                meta_words[e.get(self.key)] = HTML(format)
                        else:
                            meta_words[e.get(self.key)] = HTML(e.get(self.meta_key))
                elif isinstance(e, str):
                    words.append(e)

            completer = DshellWordCompleter(words, ignore_case=self.ignore_case,
                                            match_middle=self.match_middle, meta_dict=meta_words)
            for c in completer.get_completions(document, complete_event):
                yield c


class DshellCompleter(Completer):

    def __init__(self, options: t.Dict[str, t.Optional[t.Union[Completer, t.List[t.Dict]]]],
                 ignore_case: bool = True) -> None:

        self.options = options
        self.ignore_case = ignore_case

    @classmethod
    def from_nested_dict(cls, data: NestedDict) -> "DshellCompleter":
        """
        Create a `NestedCompleter`, starting from a nested dictionary data
        structure, like this:

        .. code::

            data = {
                'show': {
                    'version': None,
                    'interfaces': None,
                    'clock': None,
                    'ip': {'interface': {'brief'}}
                },
                'exit': None
                'enable': None
            }

        The value should be `None` if there is no further completion at some
        point. If all values in the dictionary are None, it is also possible to
        use a set instead.

        Values in this data structure can be a completers as well.
        """
        options: t.Dict[str, t.Optional[Completer]] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                options[key] = cls.from_nested_dict(value)
            else:
                options[key] = value
        return cls(options)

    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> t.Iterable[Completion]:

        # TODO: Problem with completing positionals. Solve argument resolution to know in which positional.
        try:
            # Split document.
            text = document.text_before_cursor.lstrip()
            stripped_len = len(document.text_before_cursor) - len(text)

            if text.endswith('-h') or text.endswith('--help'):
                return
            # If there is a space, check for the first term, and use a
            # subcompleter.
            if " " in text:
                first_term = text.split()[0]
                completer = self.options.get(first_term)

                # If we have a sub completer, use this for the completions.
                if isinstance(completer, Completer):
                    remaining_text = text[len(first_term):].lstrip()
                    move_cursor = len(text) - len(remaining_text) + stripped_len

                    new_document = Document(
                        remaining_text,
                        cursor_position=document.cursor_position - move_cursor,
                    )

                    for c in completer.get_completions(new_document, complete_event):
                        yield c

                # we reached the bottom subcommand. Parse to see if we have to autocomplete an argument or its value
                else:
                    options = {}
                    params = {}
                    dest_args = {}

                    if not completer:
                        return
                    for arg in completer:
                        if isinstance(arg, dict):
                            arg = [arg]
                        elif isinstance(arg, list):
                            pass
                        else:
                            # to pass command function in dict command definition
                            continue
                        for a in arg:
                            if a.get('argument').startswith('-'):
                                options.update({a.get('argument'): a})
                            else:
                                params.update({a.get('argument'): a})

                            if 'dest' in a:
                                dest_args.update({a.get('dest'): a})
                            else:
                                dest_args.update({a.get('argument').lstrip('-'): a})

                    try:
                        words = shlex.split(text)
                    except:
                        return
                    if len(words) > 0 and words[-1] in options and text.endswith(words[-1]):
                        completer = DshellWordCompleter(words=list(options.keys()))
                        for c in completer.get_completions(document, complete_event):
                            yield c
                        for p in params:
                            if 'choices' in params[p]:
                                completer = DshellWordCompleter(params[p].get("choices"))
                            elif 'completer' in params[p]:
                                completer = params[p].get('completer')
                    else:
                        parser = create_parser(completer, GuessArgumentParser(allow_abbrev=False))
                        finder = "F:I.N:D.E:R"
                        if document.char_before_cursor == ' ':
                            text = document.text + finder
                            current_word = finder
                        else:
                            text = document.text
                            current_word = document.get_word_before_cursor(WORD=True)

                        namespace = parser.parse_args(shlex.split(text)[1:])
                        values = dict(namespace._get_kwargs())

                        # find key related to current_word
                        for k, v in values.items():
                            if is_iterable_not_string(v):
                                if current_word in v:
                                    break
                            else:
                                if v == current_word:
                                    break
                        else:
                            k = None
                            v = None

                        # special case for DictAction
                        for dest, arg_def in dest_args.items():
                            if 'action' in arg_def and arg_def['action'] == DictAction and values[dest]:
                                for k, v in values[dest].items():
                                    # target
                                    if k == current_word:
                                        resp = ntwrk.get('api_1_0.orchestrationresource',
                                                         view_data={'orchestration_id': values['orchestration_id']})
                                        if resp.ok:
                                            needed_target = resp.msg['target']
                                            completer = DshellWordCompleter(
                                                [target for target in needed_target if
                                                 target not in values[dest].keys()])
                                            for c in completer.get_completions(document, complete_event):
                                                yield c
                                            return

                                    elif current_word in v:
                                        completer = arg_def.get('completer', None)
                                        for c in completer.get_completions(document, complete_event):
                                            if c.text not in v:
                                                yield c
                                        if len(v) == 0 or len(v) == 1 and v[0] == finder:
                                            return
                                k = None
                                v = None

                        # get source value
                        if k:
                            nargs = dest_args[k].get('nargs')
                            if nargs and not isinstance(nargs, int):
                                if k not in params and document.char_before_cursor == ' ':
                                    if '--' not in words:
                                        # next argument may be a positional parameter or an optional argument
                                        # if nargs '+' means that at least 1 item must be provided
                                        if not (nargs == '+' and v and len(v) - 1 == 0) and k not in params:
                                            completer = DshellWordCompleter(words=list(options.keys()))
                                            for c in completer.get_completions(document, complete_event):
                                                yield c
                                        if nargs == '*' or (nargs == '+' and v and len(v) - 1 > 0):
                                            yield Completion('--')
                                    else:
                                        for p in params:
                                            if 'choices' in params[p]:
                                                completer = DshellWordCompleter(params[p].get("choices"))
                                            elif 'completer' in params[p]:
                                                completer = params[p].get('completer')
                                            for c in completer.get_completions(document, complete_event):
                                                yield c
                                            break
                                elif k in params and document.char_before_cursor == ' ':
                                    completer = DshellWordCompleter(words=list(options.keys()))
                                    for c in completer.get_completions(document, complete_event):
                                        yield c
                            # cursor is in params (not option) it may set an optional parameter
                            elif k in params and '--' not in words:
                                completer = DshellWordCompleter(words=list(options.keys()))
                                for c in completer.get_completions(document, complete_event):
                                    yield c
                            if k in dest_args:
                                if 'choices' in dest_args[k]:
                                    completer = DshellWordCompleter(dest_args[k].get("choices"))
                                    for c in completer.get_completions(document, complete_event):
                                        if (v and c.text not in v) or v is None:
                                            yield c
                                completer = dest_args[k].get('completer', None)
                            else:
                                completer = None
                            if completer:
                                if isinstance(completer, ResourceCompleter):
                                    kwargs = dict(var_filters=values)
                                else:
                                    kwargs = {}

                                for c in completer.get_completions(document, complete_event, **kwargs):
                                    if (v and c.text not in v) or v is None:
                                        yield c
                        else:
                            completer = DshellWordCompleter(words=list(options.keys()))
                            for c in completer.get_completions(document, complete_event):
                                yield c
                            for p in params:
                                if getattr(namespace, p) is None:
                                    if 'choices' in params[p]:
                                        completer = DshellWordCompleter(params[p].get("choices"))
                                    elif 'completer' in params[p]:
                                        completer = params[p].get('completer')
                                    for c in completer.get_completions(document, complete_event):
                                        yield c

            # No space in the input: behave exactly like `WordCompleter`.
            else:
                completer = DshellWordCompleter(
                    list(self.options.keys()), ignore_case=self.ignore_case
                )
                for c in completer.get_completions(document, complete_event):
                    yield c
        except Exception as e:
            dprint(e)


class CatalogOrchNameCompleter(Completer):
    """Completer for orchestration names using the local catalog cache with fuzzy matching."""

    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        word = document.get_word_before_cursor(WORD=True)
        try:
            catalog = get_catalog()
            names = catalog.get_orchestration_names()
        except Exception:
            return
        matches = fuzzy_match(word, names)
        for name in matches:
            if name != word:
                params = catalog.get_parameters(name)
                desc = ''
                if params.get('required'):
                    desc = 'params: ' + ', '.join(str(r) for r in params['required'])
                display_meta = HTML(desc) if desc else None
                if " " in name:
                    escaped = name.replace('"', '\\"')
                    yield Completion(f'"{escaped}"', display=name, display_meta=display_meta)
                else:
                    yield Completion(name, -len(word), display_meta=display_meta)


class CatalogParamCompleter(Completer):
    """Completer for orchestration parameter names from the schema.

    Designed to be used after an orchestration name has been resolved.
    Provide ``orch_name`` when constructing, or call ``set_orch_name``
    before completion.
    """

    def __init__(self, orch_name: str = None) -> None:
        self._orch_name = orch_name

    def set_orch_name(self, orch_name: str) -> None:
        self._orch_name = orch_name

    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        if not self._orch_name:
            return
        word = document.get_word_before_cursor(WORD=True)
        try:
            catalog = get_catalog()
            params = catalog.get_parameters(self._orch_name)
        except Exception:
            return
        # Collect parameter names from schema containers (input, required, etc.)
        candidates = []
        for key, value in params.items():
            if key in ('required', 'output'):
                if isinstance(value, (list, set)):
                    candidates.extend(str(v) for v in value)
            elif isinstance(value, dict):
                candidates.extend(value.keys())
        candidates = sorted(set(candidates))
        matches = fuzzy_match(word, candidates)
        for match in matches:
            if match != word:
                yield Completion(match, -len(word))


class CatalogServerNameCompleter(Completer):
    """Completer for server names using the local catalog cache with fuzzy matching."""

    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        word = document.get_word_before_cursor(WORD=True)
        try:
            catalog = get_catalog()
            names = catalog.get_server_names()
        except Exception:
            return
        matches = fuzzy_match(word, names)
        for name in matches:
            if name != word:
                if " " in name:
                    escaped = name.replace('"', '\\"')
                    yield Completion(f'"{escaped}"', display=name)
                else:
                    yield Completion(name, -len(word))


class CatalogTargetCompleter(Completer):
    """Completer for orchestration target fields.

    Suggests target names from the orchestration schema and server names
    as possible values.
    """

    def __init__(self, orch_name: str = None) -> None:
        self._orch_name = orch_name

    def set_orch_name(self, orch_name: str) -> None:
        self._orch_name = orch_name

    def get_completions(
            self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        word = document.get_word_before_cursor(WORD=True)
        try:
            catalog = get_catalog()
        except Exception:
            return

        # If the word contains '=', complete the value part with server names
        if '=' in word:
            _, partial_value = word.rsplit('=', 1)
            server_names = catalog.get_server_names()
            matches = fuzzy_match(partial_value, server_names)
            for name in matches:
                if name != partial_value:
                    yield Completion(name, -len(partial_value))
            return

        # Otherwise, suggest target names (from orch schema) and server names
        candidates = []
        if self._orch_name:
            targets = catalog.get_target_names(self._orch_name)
            # Target names get '=' appended so the user can type the value
            for t_name in targets:
                if t_name != word:
                    matches = fuzzy_match(word, [t_name])
                    if matches:
                        yield Completion(t_name + '=', -len(word), display=t_name,
                                         display_meta=HTML('<i>target</i>'))

        # Also suggest server names directly
        server_names = catalog.get_server_names()
        matches = fuzzy_match(word, server_names)
        for name in matches:
            if name != word:
                yield Completion(name, -len(word), display_meta=HTML('<i>server</i>'))


# Catalog-backed completer instances (fuzzy, offline)
catalog_orch_name_completer = CatalogOrchNameCompleter()
catalog_param_completer = CatalogParamCompleter()
catalog_server_name_completer = CatalogServerNameCompleter()
catalog_target_completer = CatalogTargetCompleter()

server_name_completer = ResourceCompleter('api_1_0.serverlist', 'name')
server_completer = ResourceCompleter('api_1_0.serverlist', meta_key='name')
granule_completer = ResourceCompleter('api_1_0.granulelist')

orch_completer = ResourceCompleter('api_1_0.orchestrationlist', meta_html_format="<b>{name}</b>, ver <i>{version}</i>",
                                   filters=['--version'])
orch_name_completer = ResourceCompleter('api_1_0.orchestrationlist', 'name', filters=['--version'])
orch_ver_completer = ResourceCompleter('api_1_0.orchestrationlist', 'version', filters=['--name'])

action_completer = ResourceCompleter('api_1_0.actiontemplatelist',
                                     meta_html_format="<b>{name}</b>, ver <i>{version}</i>",
                                     filters=['--version'])
action_name_completer = ResourceCompleter('api_1_0.actiontemplatelist', 'name', filters=['--version'])
action_ver_completer = ResourceCompleter('api_1_0.actiontemplatelist', 'version', filters=['--name'])

software_completer = ResourceCompleter('api_1_0.softwarelist', meta_html_format="<b>{name}</b>, ver <i>{version}</i>", )
software_name_completer = ResourceCompleter('api_1_0.softwarelist', 'name', filters=['--version'])
software_ver_completer = ResourceCompleter('api_1_0.softwarelist', 'version', filters=['software'])
software_family_completer = ResourceCompleter('api_1_0.softwarelist', 'family')

logfed_completer = ResourceCompleter('api_1_0.loglist', resource_params={'params': 'human'},
                                     meta_html_format="<b>{target}</b>, "
                                                      "<i>{src_server}</i> -> "
                                                      "<i>{dst_server}</i>")
file_completer = ResourceCompleter('api_1_0.filelist', resource_params={'params': 'human'},
                                   meta_html_format="{src_server}:<b>{target}</b>", )
file_dest_completer = ResourceCompleter('api_1_0.fileserverassociationlist', 'version',
                                        resource_params={'params': 'human'},
                                        filters=['file_id'])

logger_completer = DshellWordCompleter([l for l in logging.root.manager.loggerDict.keys() if l.startswith('dshell')])
