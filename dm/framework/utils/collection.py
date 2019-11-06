import inspect
import typing as t
from functools import singledispatch

SliceAll = slice(None)
generator = type(e for e in ())


@singledispatch
def freeze(obj):
    """Returns immutable copy of the `obj`"""
    return obj


@freeze.register(dict)
def _(d: dict):
    return frozendict((k, freeze(v)) for k, v in d.items())


@freeze.register(list)
def _(l: list):
    return tuple(freeze(v) for v in l)


@freeze.register(set)
def _(s: set):
    return frozenset(freeze(v) for v in s)


class _Missing:
    def __bool__(self):
        return False

    def __copy__(self):
        return self

    def __deepcopy__(self, _):
        return self

    def __repr__(self):
        return "<marshmallow.missing>"


# Singleton value that indicates that a field's value is missing from input
# dict passed to :meth:`Schema.load`. If the field's value is not required,
# it's ``default`` value is used.
missing = _Missing()


def sget(target, key: str, default: t.Any = None):
    """
    structure-get, a function simmilar to dict's 'get' method, which can resolve inner
    structure of keys. A string-typed key may be composed of series of keys (for maps)
    or indexes (for sequences), concatenated with dots. The method cat take a default value,
    just as dict.get does.

    An example:
    >>> bunch = Bunch(foo={'bar': ['value']})
    >>> assert sget(bunch, 'foo.bar.0') == 'value'
    >>> assert sget(bunch, 'foo.baz', 42) == 42
    """
    key_iter = key.split('.') if hasattr(key, 'split') else [key]
    value = target
    for part in key_iter:
        try:
            # attribute access
            value = getattr(value, part)
        except (TypeError, AttributeError):
            try:
                # key access
                value = value[part]
            except KeyError:
                return default
            except TypeError:
                # index access
                try:
                    value = value[int(part)]
                except (TypeError, ValueError, IndexError):
                    return default
    return value


def is_generator(obj):
    """Return True if ``obj`` is a generator
    """
    return inspect.isgeneratorfunction(obj) or inspect.isgenerator(obj)


def is_iterable(obj):
    """
    Are we being asked to look up a list of things, instead of a single thing?
    We check for the `__iter__` attribute so that this can cover types that
    don't have to be known by this module, such as NumPy arrays.
    Strings, however, should be considered as atomic values to look up, not
    iterables.
    We don't need to check for the Python 2 `unicode` type, because it doesn't
    have an `__iter__` attribute anyway.
    """
    return hasattr(obj, '__iter__') and not isinstance(obj, str)


def is_collection(obj):
    """Return True if ``obj`` is a collection type, e.g list, tuple, queryset."""
    return is_iterable(obj) and not isinstance(obj, t.Mapping)


def is_instance_or_subclass(val, class_):
    """Return True if ``val`` is either a subclass or instance of ``class_``."""
    try:
        return issubclass(val, class_)
    except TypeError:
        return isinstance(val, class_)


# noinspection PyPep8Naming
class frozendict(dict):  # noqa: N801
    """
    Frozen (immutable) version of dict. Name is left to be consistent with
    set/frozenset pair.

    The code is taken from:
    code.activestate.com/recipes/414283-frozen-dictionaries/
    """

    def __not_implemented__(self, *args, **kwargs):
        raise AttributeError("A frozendict cannot be modified.")

    __delitem__ = __setitem__ = clear = \
        pop = popitem = setdefault = update = __not_implemented__

    def __copy__(self):
        """
        Addresses the problem with copy.copy(frozendict()) and its default copier (which asserts
        mutability of the target).
        """
        return frozendict(dict.copy(self))

    def __new__(cls, *args, **kwargs):
        new = dict.__new__(cls)
        combined_kwargs = {}
        for structure in args + (kwargs,):
            if isinstance(structure, (list, generator)):
                combined_kwargs.update({v0: v1 for v0, v1 in structure})
            elif isinstance(structure, dict):
                combined_kwargs.update(structure)
        frozen_structure = [(freeze(k), freeze(v)) for k, v in combined_kwargs.items()]
        dict.__init__(new, frozen_structure)
        return new

    def __hash__(self):
        try:
            return self._cached_hash
        except AttributeError:
            self._cached_hash = hash(frozenset(self.items()))
            return self._cached_hash

    def __repr__(self):
        return "frozendict(%s)" % dict.__repr__(self)


class Bunch(dict):
    """
    Dict-like object which gives attribute access to its components.

    An example:
    >>> bunch = Bunch(foo='bar')
    >>> assert bunch.foo == 'bar'
    >>> bunch.foo = {'bar': ['baz']}
    >>> assert bunch['foo'] = {'bar': ['baz']}
    """

    def __getattr__(self, key: str) -> t.Any:
        """
        Gets key if it exists, otherwise throws AttributeError.
        NB __getattr__ is only called if key is not found in normal places.

        :raises: AttributeError
        """
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key: str, value: t.Any) -> None:
        """
        Sets value under the specified key. Translates TypeError
        (ie. unhashable keys) to AttributeError.

        :raises: AttributeError
        """
        try:
            self[key] = value
        except (KeyError, TypeError):
            raise AttributeError(key)

    def __delattr__(self, key: str) -> None:
        """
        Deletes attribute k if it exists, otherwise deletes key k. A KeyError
        raised by deleting the key--such as when the key is missing--will
        propagate as an AttributeError instead.

        :raises: AttributeError
        """
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)

    def __repr__(self) -> str:
        """
        Invertible string-form of a Bunch.
        """
        keys = list(self.keys())
        keys.sort()
        return '%s(%s)' % (
            self.__class__.__name__,
            ', '.join(['%s=%r' % (key, self[key]) for key in keys])
        )
