from unittest import TestCase

from dm.framework.data.predicate import var, where, Predicate, Var  # noqa


class TestConfig(TestCase):

    def setUp(self) -> None:
        self.example_dict = {
            'foo': 1,
            'bar': {
                'baz': {'a': 1},
            }
        }


class TestConstructors(TestConfig):

    def test_no_path(self):
        with self.assertRaises(ValueError):
            Var() == 2

    def test_multiple_path_getattr(self):
        predicate = Var().bar.baz.a == 1
        self.assertTrue(predicate(self.example_dict))

    def test_multiple_path_getitem(self):
        predicate = Var()['bar.baz.a'] == 1
        self.assertTrue(predicate(self.example_dict))

    def test_orm_usage(self):
        d = Var()
        predicate1 = d.foo == 1  # type: Predicate
        predicate2 = d.bar.baz == {'a': 1}  # type: Predicate
        self.assertTrue(predicate1(self.example_dict))
        self.assertTrue(predicate2(self.example_dict))

    def test_where_usage(self):
        predicate1 = where('foo') == 1  # type: Predicate
        predicate2 = where('bar.baz') == {'a': 1}  # type: Predicate
        self.assertIsNone(predicate1.var_name)
        self.assertIsNone(predicate2.var_name)
        self.assertTrue(predicate1(self.example_dict))
        self.assertTrue(predicate2(self.example_dict))

    def test_var_usage(self):
        predicate1 = var('foo') == 1  # type: Predicate
        predicate2 = var('bar.baz') == {'a': 1}  # type: Predicate
        self.assertEqual(predicate1.var_name, 'foo')
        self.assertEqual(predicate2.var_name, 'baz')
        self.assertTrue(predicate1(self.example_dict))
        self.assertTrue(predicate2(self.example_dict))


class TestAlgebraicOperations(TestCase):

    def test_eq(self):
        predicate = Var().value == 1  # type: Predicate
        assert predicate({'value': 1})
        assert not predicate({'value': 2})
        assert hash(predicate)

        predicate = Var().value == [0, 1]  # type: Predicate
        assert predicate({'value': [0, 1]})
        assert not predicate({'value': [0, 1, 2]})
        assert hash(predicate)

    def test_ne(self):
        predicate = Var().value != 1  # type: Predicate
        assert predicate({'value': 2})
        assert not predicate({'value': 1})
        assert hash(predicate)

        predicate = Var().value != [0, 1]  # type: Predicate
        assert predicate({'value': [0, 1, 2]})
        assert not predicate({'value': [0, 1]})
        assert hash(predicate)

    def test_lt(self):
        predicate = Var().value < 1  # type: Predicate
        assert predicate({'value': 0})
        assert not predicate({'value': 1})
        assert hash(predicate)

    def test_le(self):
        predicate = Var().value <= 1  # type: Predicate
        assert predicate({'value': 0})
        assert predicate({'value': 1})
        assert not predicate({'value': 2})
        assert hash(predicate)

    def test_gt(self):
        predicate = Var().value > 1  # type: Predicate
        assert predicate({'value': 2})
        assert not predicate({'value': 1})
        assert hash(predicate)

    def test_ge(self):
        predicate = Var().value >= 1  # type: Predicate
        assert predicate({'value': 2})
        assert predicate({'value': 1})
        assert not predicate({'value': 0})
        assert hash(predicate)


class TestLogicalOperations(TestCase):

    def test_or(self):
        predicate = (
                (Var().val1 == 1) |
                (Var().val2 == 2)
        )  # type: Predicate
        assert predicate({'val1': 1})
        assert predicate({'val2': 2})
        assert predicate({'val1': 1, 'val2': 2})
        assert not predicate({'val1': '', 'val2': ''})
        assert hash(predicate)

    def test_and(self):
        predicate = (
                (Var().val1 == 1) &
                (Var().val2 == 2)
        )  # type: Predicate
        assert predicate({'val1': 1, 'val2': 2})
        assert not predicate({'val1': 1})
        assert not predicate({'val2': 2})
        assert not predicate({'val1': '', 'val2': ''})
        assert hash(predicate)

    def test_not(self):
        predicate = ~(Var().val1 == 1)  # type: Predicate
        assert predicate({'val1': 5, 'val2': 2})
        assert not predicate({'val1': 1, 'val2': 2})
        assert hash(predicate)

        predicate = (
                (~ (Var().val1 == 1)) &
                (Var().val2 == 2)
        )  # type: Predicate
        assert predicate({'val1': '', 'val2': 2})
        assert predicate({'val2': 2})
        assert not predicate({'val1': 1, 'val2': 2})
        assert not predicate({'val1': 1})
        assert not predicate({'val1': '', 'val2': ''})
        assert hash(predicate)

    def test_any(self):
        predicate = Var().followers.any(Var().name == 'don')  # type: Predicate

        assert predicate({'followers': [{'name': 'don'}, {'name': 'john'}]})
        assert not predicate({'followers': 1})
        assert not predicate({})
        assert hash(predicate)

        predicate = Var().followers.any(Var().num.matches('\\d+'))  # type: Predicate
        assert predicate({'followers': [{'num': '12'}, {'num': 'abc'}]})
        assert not predicate({'followers': [{'num': 'abc'}]})
        assert hash(predicate)

        predicate = Var().followers.any(['don', 'jon'])  # type: Predicate
        assert predicate({'followers': ['don', 'greg', 'bill']})
        assert not predicate({'followers': ['greg', 'bill']})
        assert not predicate({})
        assert hash(predicate)

        predicate = Var().followers.any([{'name': 'don'}, {'name': 'john'}])  # type: Predicate
        assert predicate({'followers': [{'name': 'don'}, {'name': 'greg'}]})
        assert not predicate({'followers': [{'name': 'greg'}]})
        assert hash(predicate)

    def test_all(self):
        predicate = Var().followers.all(Var().name == 'don')  # type: Predicate
        assert predicate({'followers': [{'name': 'don'}]})
        assert not predicate({'followers': [{'name': 'don'}, {'name': 'john'}]})
        assert hash(predicate)

        predicate = Var().followers.all(Var().num.matches('\\d+'))  # type: Predicate
        assert predicate({'followers': [{'num': '123'}, {'num': '456'}]})
        assert not predicate({'followers': [{'num': '123'}, {'num': 'abc'}]})
        assert hash(predicate)

        predicate = Var().followers.all(['don', 'john'])  # type: Predicate
        assert predicate({'followers': ['don', 'john', 'greg']})
        assert not predicate({'followers': ['don', 'greg']})
        assert not predicate({})
        assert hash(predicate)

        predicate = Var().followers.all([{'name': 'john'}, {'age': 17}])  # type: Predicate
        assert predicate({'followers': [{'name': 'john'}, {'age': 17}]})
        assert not predicate({'followers': [{'name': 'john'}, {'age': 18}]})
        assert hash(predicate)


class TestDbLikeOperations(TestCase):

    def test_has_key(self):
        predicate = Var().val3.exists()  # type: Predicate

        assert predicate({'val3': 1})
        assert not predicate({'val1': 1, 'val2': 2})
        assert hash(predicate)

    def test_regex(self):
        predicate = Var().val.matches(r'\d{2}\.')  # type: Predicate

        assert predicate({'val': '42.'})
        assert not predicate({'val': '44'})
        assert not predicate({'val': 'ab.'})
        assert not predicate({'': None})
        assert hash(predicate)

        predicate = Var().val.search(r'\d+')  # type: Predicate

        assert predicate({'val': 'ab3'})
        assert not predicate({'val': 'abc'})
        assert not predicate({'val': ''})
        assert not predicate({'': None})
        assert hash(predicate)

    def test_custom(self):
        def test(value):
            return value == 42

        predicate = Var().val.test(test)  # type: Predicate

        assert predicate({'val': 42})
        assert not predicate({'val': 40})
        assert not predicate({'val': '44'})
        assert not predicate({'': None})
        assert hash(predicate)

    def test_custom_with_params(self):
        def test(value, minimum, maximum):
            return minimum <= value <= maximum

        predicate = Var().val.test(test, 1, 10)  # type: Predicate

        assert predicate({'val': 5})
        assert not predicate({'val': 0})
        assert not predicate({'val': 11})
        assert not predicate({'': None})
        assert hash(predicate)

    def test_has(self):
        predicate = Var().key1.key2.exists()  # type: Predicate
        str(predicate)  # This used to cause a bug...

        assert predicate({'key1': {'key2': {'key3': 1}}})
        assert predicate({'key1': {'key2': 1}})
        assert not predicate({'key1': 3})
        assert not predicate({'key1': {'key1': 1}})
        assert not predicate({'key2': {'key1': 1}})
        assert hash(predicate)

        predicate = Var().key1.key2 == 1  # type: Predicate

        assert predicate({'key1': {'key2': 1}})
        assert not predicate({'key1': {'key2': 2}})
        assert hash(predicate)

        # Nested has: key exists
        predicate = Var().key1.key2.key3.exists()  # type: Predicate
        assert predicate({'key1': {'key2': {'key3': 1}}})
        # Not a dict
        assert not predicate({'key1': 1})
        assert not predicate({'key1': {'key2': 1}})
        # Wrong key
        assert not predicate({'key1': {'key2': {'key0': 1}}})
        assert not predicate({'key1': {'key0': {'key3': 1}}})
        assert not predicate({'key0': {'key2': {'key3': 1}}})

        assert hash(predicate)

        # Nested has: check for value
        predicate = Var().key1.key2.key3 == 1  # type: Predicate
        assert predicate({'key1': {'key2': {'key3': 1}}})
        assert not predicate({'key1': {'key2': {'key3': 0}}})
        assert hash(predicate)

        # Test special methods: regex matches
        predicate = Var().key1.value.matches(r'\d+')  # type: Predicate
        assert predicate({'key1': {'value': '123'}})
        assert not predicate({'key2': {'value': '123'}})
        assert not predicate({'key2': {'value': 'abc'}})
        assert hash(predicate)

        # Test special methods: regex contains
        predicate = Var().key1.value.search(r'\d+')  # type: Predicate
        assert predicate({'key1': {'value': 'a2c'}})
        assert not predicate({'key2': {'value': 'a2c'}})
        assert not predicate({'key2': {'value': 'abc'}})
        assert hash(predicate)

        # Test special methods: nested has and regex matches
        predicate = Var().key1.x.y.matches(r'\d+')  # type: Predicate
        assert predicate({'key1': {'x': {'y': '123'}}})
        assert not predicate({'key1': {'x': {'y': 'abc'}}})
        assert hash(predicate)

        # Test special method: nested has and regex contains
        predicate = Var().key1.x.y.search(r'\d+')  # type: Predicate
        assert predicate({'key1': {'x': {'y': 'a2c'}}})
        assert not predicate({'key1': {'x': {'y': 'abc'}}})
        assert hash(predicate)

        # Test special methods: custom tests
        predicate = Var().key1.int.test(lambda x: x == 3)  # type: Predicate
        assert predicate({'key1': {'int': 3}})
        assert hash(predicate)


class TestOther(TestConfig):

    def test_predicate_eq(self):
        """One mistakenly try to compare Predicate instance with a value"""
        predicate = Var().foo == 1
        assert not (predicate == self.example_dict)

    def test_hash(self):
        s = {
            Var().key1 == 2,
            Var().key1.key2.key3.exists(),
            Var().key1.exists() & Var().key2.exists(),
            Var().key1.exists() | Var().key2.exists(),
        }

        assert (Var().key1 == 2) in s
        assert (Var().key1.key2.key3.exists()) in s

        # Commutative property of & and |
        assert (Var().key1.exists() & Var().key2.exists()) in s
        assert (Var().key2.exists() & Var().key1.exists()) in s
        assert (Var().key1.exists() | Var().key2.exists()) in s
        assert (Var().key2.exists() | Var().key1.exists()) in s

    def test_two_variable_predicate(self):
        predicate1 = var('foo') == var('bar.baz.a')  # type: Predicate
        predicate2 = var('foo') == var('bar.baz')  # type: Predicate
        assert predicate1(self.example_dict)
        assert not predicate2(self.example_dict)
