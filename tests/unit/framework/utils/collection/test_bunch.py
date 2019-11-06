from unittest import TestCase

from dm.framework.utils.collection import Bunch


class TestBunch(TestCase):

    def setUp(self) -> None:
        self.bunch = Bunch()
        self.bunch_foo = Bunch(foo='bar')

    def test_getattr(self):
        assert self.bunch_foo.foo == 'bar'
        with self.assertRaises(AttributeError):
            # noinspection PyStatementEffect
            self.bunch_foo.bar

    def test_getitem(self):
        assert self.bunch_foo['foo'] == 'bar'
        with self.assertRaises(KeyError):
            # noinspection PyStatementEffect
            self.bunch_foo['bar']

    def test_setattr(self):
        self.bunch.foo = 'bar'
        assert self.bunch['foo'] == 'bar'

    def test_setitem(self):
        self.bunch['foo'] = 'bar'
        assert self.bunch.foo == 'bar'

    def test_delattr(self):
        del self.bunch_foo.foo
        assert 'foo' not in self.bunch_foo
        with self.assertRaises(AttributeError):
            del self.bunch_foo.bar

    def test_delitem(self):
        del self.bunch_foo['foo']
        assert 'foo' not in self.bunch_foo
        with self.assertRaises(KeyError):
            del self.bunch_foo['bar']

    def test_repr(self):
        assert self.bunch_foo == eval(repr(self.bunch_foo))

