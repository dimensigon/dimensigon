import argparse
import ast
import functools
import re
import sys
import types
from typing import Text, Optional, TypeVar, NoReturn

if sys.version_info < (3, 7):
    def _copy_items(items):
        if items is None:
            return []
        # The copy module is used only in the 'append' and 'append_const'
        # actions, and it is needed only when the default value isn't a list.
        # Delay its import for speeding up the common case.
        if type(items) is list:
            return items[:]
        import copy
        return copy.copy(items)


    class _AppendAction(argparse.Action):

        def __init__(self,
                     option_strings,
                     dest,
                     nargs=None,
                     const=None,
                     default=None,
                     type=None,
                     choices=None,
                     required=False,
                     help=None,
                     metavar=None):
            if nargs == 0:
                raise ValueError('nargs for append actions must be != 0; if arg '
                                 'strings are not supplying the value to append, '
                                 'the append const action may be more appropriate')
            if const is not None and nargs != argparse.OPTIONAL:
                raise ValueError('nargs must be %r to supply const' % argparse.OPTIONAL)
            super(_AppendAction, self).__init__(
                option_strings=option_strings,
                dest=dest,
                nargs=nargs,
                const=const,
                default=default,
                type=type,
                choices=choices,
                required=required,
                help=help,
                metavar=metavar)

        def __call__(self, parser, namespace, values, option_string=None):
            items = getattr(namespace, self.dest, None)
            items = _copy_items(items)
            items.append(values)
            setattr(namespace, self.dest, items)
else:
    _copy_items = argparse._copy_items
    _AppendAction = argparse._AppendAction


class ArgumentParserRaise(argparse.ArgumentParser):

    def exit(self, status: int = ..., message: Optional[Text] = ...) -> NoReturn:
        if message != ...:
            print(message)
        raise SystemExit


_T = TypeVar('_T')
import re as _re

class GuessArgumentParser(ArgumentParserRaise):

    # =====================================
    # Command line argument parsing methods
    # =====================================
    def parse_args(self, args=None, namespace=None):
        args, argv = self.parse_known_args(args, namespace)
        return args

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # args default to the system args
            args = argparse._sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = argparse.Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not argparse.SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not argparse.SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments and exit if there are any errors
        try:
            namespace, args = self._parse_known_args(args, namespace)
            if hasattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR):
                args.extend(getattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR))
                delattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR)
            return namespace, args
        except argparse.ArgumentError:
            err = argparse._sys.exc_info()[1]
            self.error(str(err))

    def _check_value(self, action, value):
        pass

    def _get_nargs_pattern(self, action, action_slices=None):
        # in all examples below, we have to allow for '--' args
        # which are represented as '-' in the pattern
        nargs = action.nargs

        # the default (None) is assumed to be a single argument
        if nargs is None:
            nargs_pattern = '(-*A-*)'

        # allow zero or one arguments
        elif nargs == argparse.OPTIONAL:
            nargs_pattern = '(-*A?-*)'

        # allow zero or more arguments
        elif nargs == argparse.ZERO_OR_MORE:
            nargs_pattern = '(-*[A-]*)'

        # allow one or more arguments
        elif nargs == argparse.ONE_OR_MORE:
            nargs_pattern = '(-*A[A-]*)'

        # allow any number of options or arguments
        elif nargs == argparse.REMAINDER:
            nargs_pattern = '([-AO]*)'

        # allow one argument followed by any number of options or arguments
        elif nargs == argparse.PARSER:
            nargs_pattern = '(-*A[-AO]*)'

        # all others should be integers
        else:
            if action_slices and action == action_slices[-1]:
                nargs_pattern = '(-*[A-]{,%s})' % nargs
            else:
                nargs_pattern = '(-*%s-*)' % '-*'.join('A' * nargs)

        # if this is an optional action, -- is not allowed
        if action.option_strings:
            nargs_pattern = nargs_pattern.replace('-*', '')
            nargs_pattern = nargs_pattern.replace('-', '')

        # return the pattern
        return nargs_pattern

    def _match_argument(self, action, arg_strings_pattern):
        # match the pattern for this action to the arg strings
        nargs_pattern = self._get_nargs_pattern(action, arg_strings_pattern)
        match = _re.match(nargs_pattern, arg_strings_pattern)

        # raise an exception if we weren't able to find a match
        if match is None:
            return 0

        # return the number of arguments matched
        return len(match.group(1))

    def _match_arguments_partial(self, actions, arg_strings_pattern):
        # progressively shorten the actions list by slicing off the
        # final actions until we find a match
        result = []
        for i in range(len(actions), 0, -1):
            actions_slice = actions[:i]
            pattern = ''.join([self._get_nargs_pattern(action, actions_slice)
                               for action in actions_slice])
            match = _re.match(pattern, arg_strings_pattern)
            if match is not None:
                result.extend([len(string) for string in match.groups()])
                break

        # return the list of arg string counts
        return result

    def _parse_known_args(self, arg_strings, namespace):

        # map all mutually exclusive arguments to the other arguments
        # they can't occur with
        action_conflicts = {}

        # find all option indices, and determine the arg_string_pattern
        # which has an 'O' if there is an option at an index,
        # an 'A' if there is an argument, or a '-' if there is a '--'
        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):

            # all args after -- are non-options
            if arg_string == '--':
                arg_string_pattern_parts.append('-')
                for arg_string in arg_strings_iter:
                    arg_string_pattern_parts.append('A')

            # otherwise, add the arg to the arg strings
            # and note the index if it was an option
            else:
                option_tuple = self._parse_optional(arg_string)
                if option_tuple is None:
                    pattern = 'A'
                else:
                    option_string_indices[i] = option_tuple
                    pattern = 'O'
                arg_string_pattern_parts.append(pattern)

        # join the pieces together to form the pattern
        arg_strings_pattern = ''.join(arg_string_pattern_parts)

        # converts arg strings to the appropriate and then takes the action
        seen_actions = set()
        seen_non_default_actions = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            # error if this argument is not allowed with other previously
            # seen arguments, assuming that actions that use the default
            # value don't really count as "present"
            if argument_values is not action.default:
                seen_non_default_actions.add(action)

            # take the action if we didn't receive a SUPPRESS value
            # (e.g. from a default)
            if argument_values is not argparse.SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # function to convert arg_strings into an optional action
        def consume_optional(start_index):

            # get the optional identified at this index
            option_tuple = option_string_indices[start_index]
            action, option_string, explicit_arg = option_tuple

            # identify additional optionals in the same arg string
            # (e.g. -xyz is the same as -x -y -z if no args are required)
            match_argument = self._match_argument
            action_tuples = []
            while True:

                # if we found no optional action, skip it
                if action is None:
                    extras.append(arg_strings[start_index])
                    return start_index + 1

                # if there is an explicit argument, try to match the
                # optional's string arguments to only this
                if explicit_arg is not None:
                    arg_count = match_argument(action, 'A')

                    # if the action is a single-dash option and takes no
                    # arguments, try to parse more single-dash options out
                    # of the tail of the option string
                    chars = self.prefix_chars
                    if arg_count == 0 and option_string[1] not in chars:
                        action_tuples.append((action, [], option_string))
                        char = option_string[0]
                        option_string = char + explicit_arg[0]
                        new_explicit_arg = explicit_arg[1:] or None
                        optionals_map = self._option_string_actions
                        if option_string in optionals_map:
                            action = optionals_map[option_string]
                            explicit_arg = new_explicit_arg

                    # if the action expect exactly one argument, we've
                    # successfully matched the option; exit the loop
                    elif arg_count == 1:
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break

                # if there is no explicit argument, try to match the
                # optional's string arguments with the following strings
                # if successful, exit the loop
                else:
                    start = start_index + 1
                    selected_patterns = arg_strings_pattern[start:]
                    arg_count = match_argument(action, selected_patterns)
                    stop = start + arg_count
                    args = arg_strings[start:stop]
                    action_tuples.append((action, args, option_string))
                    break

            # add the Optional to the list and return the index at which
            # the Optional's string args stopped
            assert action_tuples
            for action, args, option_string in action_tuples:
                take_action(action, args, option_string)
            return stop

        # the list of Positionals left to be parsed; this is modified
        # by consume_positionals()
        positionals = self._get_positional_actions()

        # function to convert arg_strings into positional actions
        def consume_positionals(start_index):
            # match as many Positionals as possible
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)

            # slice off the appropriate arg strings for each Positional
            # and add the Positional and its args to the list
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index: start_index + arg_count]
                start_index += arg_count
                take_action(action, args)

            # slice off the Positionals that we just parsed and return the
            # index at which the Positionals' string args stopped
            positionals[:] = positionals[len(arg_counts):]
            return start_index

        # consume Positionals and Optionals alternately, until we have
        # passed the last option string
        extras = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1
        while start_index <= max_option_string_index:

            # consume any Positionals preceding the next option
            next_option_string_index = min([
                index
                for index in option_string_indices
                if index >= start_index])
            if start_index != next_option_string_index:
                positionals_end_index = consume_positionals(start_index)

                # only try to parse the next optional if we didn't consume
                # the option string during the positionals parsing
                if positionals_end_index > start_index:
                    start_index = positionals_end_index
                    continue
                else:
                    start_index = positionals_end_index

            # if we consumed all the positionals we could and we're not
            # at the index of an option string, there were extra arguments
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                start_index = next_option_string_index

            # consume the next optional and any arguments for it
            start_index = consume_optional(start_index)

        # consume any positionals following the last Optional
        stop_index = consume_positionals(start_index)

        # if we didn't consume all the argument strings, there were extras
        extras.extend(arg_strings[stop_index:])

        # make sure all required actions were present and also convert
        # action defaults which were not given as arguments
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                if action.required:
                    required_actions.append(argparse._get_action_name(action))
                else:
                    # Convert action default now instead of doing it before
                    # parsing arguments to avoid calling convert functions
                    # twice (which may fail) if the argument was given, but
                    # only if it was defined already in the namespace
                    if (action.default is not None and
                            isinstance(action.default, str) and
                            hasattr(namespace, action.dest) and
                            action.default is getattr(namespace, action.dest)):
                        setattr(namespace, action.dest,
                                self._get_value(action, action.default))

        # make sure all required groups had one option present
        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break

        # return the updated namespace and the extra arguments
        return namespace, extras


class DictAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super(DictAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        container = getattr(namespace, self.dest, None)
        if container is None:
            setattr(namespace, self.dest, {})
            container = getattr(namespace, self.dest, None)

        for value in values:
            if '=' in value:
                target, host = value.split('=')
                if ',' in host:
                    host = host.split(',')
                else:
                    host = [host]
                if target in container:
                    container[target].extend(host)
                else:
                    container.update({target: host})
            else:
                if 'all' not in container:
                    container.update({'all': [value]})
                else:
                    container['all'].append(value)


class ExtendAction(_AppendAction):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.extend(values)
        setattr(namespace, self.dest, items)


class ParamAction(argparse.Action):
    exp = re.compile(r"^([\"']?)([\w\-_]+):(.*?)\1$", re.MULTILINE | re.DOTALL)

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        for param in values:
            match = self.exp.search(param)
            if not match:
                raise ValueError(
                    f"Not a valid parameter '{param}'. Must contain a KEY:VALUE. Ex. string-key:'string-value' or "
                    f"integer-key:12345 or list-key:[1,2]")
            else:
                mark, key, value = match.groups()
                try:
                    value = ast.literal_eval(value)
                except Exception:
                    value = value.encode().decode('unicode-escape')
            if isinstance(value, str) and value.startswith('@'):
                file = value.strip('@')
                value = open(file, 'r').read()

            container = getattr(namespace, self.dest, None)
            if container is None:
                setattr(namespace, self.dest, {key: value})
            else:
                container.update({key: value})


def create_parser(data, parser=None) -> ArgumentParserRaise:
    if parser is None:
        parser = ArgumentParserRaise()

    if isinstance(parser, GuessArgumentParser):
        pop_keys = ('argument', 'completer', 'type')
    else:
        pop_keys = ('argument', 'completer')
    if isinstance(data, dict):
        subparsers = parser.add_subparsers()
        for k, v in data.items():
            i_parser = subparsers.add_parser(k)
            if isinstance(v, dict):
                create_parser(v, parser=i_parser)
            elif isinstance(v, list):
                for arg in v:
                    if isinstance(arg, list):
                        group = i_parser.add_mutually_exclusive_group()
                        for a in arg:
                            arguments = a['argument'] if isinstance(a['argument'], list) else [a['argument']]
                            group.add_argument(*arguments,
                                               **{kk: vv for kk, vv in a.items() if
                                                  kk not in pop_keys})
                    elif isinstance(arg, (types.FunctionType, functools.partial)):
                        i_parser.set_defaults(func=arg)
                    else:
                        arguments = arg['argument'] if isinstance(arg['argument'], list) else [arg['argument']]
                        i_parser.add_argument(*arguments,
                                              **{kk: vv for kk, vv in arg.items() if
                                                 kk not in pop_keys})
    else:
        for arg in data:
            if isinstance(arg, list):
                group = parser.add_mutually_exclusive_group()
                for a in arg:
                    arguments = a['argument'] if isinstance(a['argument'], list) else [a['argument']]
                    group.add_argument(*arguments,
                                       **{kk: vv for kk, vv in a.items() if kk not in pop_keys})
            elif isinstance(arg, (types.FunctionType, functools.partial)):
                parser.set_defaults(func=arg)
            else:
                arguments = arg['argument'] if isinstance(arg['argument'], list) else [arg['argument']]
                parser.add_argument(*arguments,
                                    **{kk: vv for kk, vv in arg.items() if kk not in pop_keys})
    return parser
