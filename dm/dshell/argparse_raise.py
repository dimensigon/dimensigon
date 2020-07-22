import argparse
import types
from typing import Text, Optional, TypeVar, NoReturn


class ArgumentParserRaise(argparse.ArgumentParser):

    def exit(self, status: int = ..., message: Optional[Text] = ...) -> NoReturn:
        if message != ...:
            print(message)
        raise SystemExit


_T = TypeVar('_T')


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
                try:
                    action(self, namespace, argument_values, option_string)
                except:
                    pass

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
            setattr(namespace, self.dest, {values[0]: values[1:]})
        else:
            container.update({values[0]: values[1:]})


class ParamAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super(ParamAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) == 1:

            if '=' not in values[0]:
                raise ValueError(f"Not a valid parameter '{values}'")
            else:
                key, value = values[0].split('=', 1)
        else:
            key = values[0]
            value = ' '.join(values[1:])
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
                            group.add_argument(a['argument'],
                                               **{kk: vv for kk, vv in a.items() if
                                                  kk not in pop_keys})
                    elif isinstance(arg, types.FunctionType):
                        i_parser.set_defaults(func=arg)
                    else:
                        i_parser.add_argument(arg['argument'],
                                              **{kk: vv for kk, vv in arg.items() if
                                                 kk not in pop_keys})
    else:
        for arg in data:
            if isinstance(arg, list):
                group = parser.add_mutually_exclusive_group()
                for a in arg:
                    group.add_argument(a['argument'],
                                       **{kk: vv for kk, vv in a.items() if kk not in pop_keys})
            elif isinstance(arg, types.FunctionType):
                parser.set_defaults(func=arg)
            else:
                parser.add_argument(arg['argument'],
                                    **{kk: vv for kk, vv in arg.items() if kk not in pop_keys})
    return parser
