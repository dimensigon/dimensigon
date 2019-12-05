import typing as t
from unittest import TestCase, mock

from dm.framework.data.dao import InMemoryDao
from dm.framework.data.dao.db import DbDao
from dm.framework.data.predicate import where
import dm.framework.exceptions as exc

pred_a = where('char') == 'a'
pred_not_a = ~(where('char') == 'a')
pred_c = where('char') == 'c'
pred_z = where('char') == 'z'


def get_ids(objects: t.Iterable):
    return [dto.get('id') for dto in objects]


class TestDbDao(TestCase):

    def setUp(self) -> None:
        self.content = [{'id': i, 'char': c, 'is_a': c == 'a'} for c, i in zip('abc', range(1, 4))]
        self.mock_container = mock.Mock()
        self.dao = DbDao('char_table', ':memory:')
        self.dao.con.execute("CREATE TABLE char_table (id INTEGER PRIMARY KEY, char  VARCHAR(1), is_a BOOLEAN)")
        self.dao.con.executemany("INSERT INTO char_table values (?, ?, ?)", [tuple(item.values()) for item in self.content])

    def test_initial_content(self):
        self.assertListEqual([dict(dto) for dto in self.dao.all()], self.content)

    # Dao.all
    def test_all(self):
        assert get_ids(self.dao.all()) == [1, 2, 3]

    # # Dao.one
    # def test_one(self):
    #     dto = self.dao.one()
    #     self.assertIsInstance(dto, Dto)
    #     self.assertEqual(dto, self.content[0])

    # QueryChain.filter
    def test_multiple_filter_success(self):
        predicate = self.dao.filter(pred_not_a).filter(pred_c)
        values = [dict(dto) for dto in predicate]
        self.assertListEqual(values, [self.content[2]])

    # QueryChain.filter_by
    def test_filter_by_success(self):
        self.assertListEqual([dict(dto) for dto in self.dao.filter(pred_not_a).filter_by(id_=3)],
                             [self.content[2]])

    def test_filter_by_both_arguments_error(self):
        with self.assertRaises(exc.QueryError):
            assert self.dao.all().filter_by(id_=3, ids=[3, 5])

    def test_filter_by_two_times_error(self):
        with self.assertRaises(exc.QueryError):
            assert self.dao.all().filter_by(id_=3).filter_by(id_=5)

    # QueryChain.get
    def test_get_success(self):
        data = self.dao.get(1)
        data.update({'added': True})
        self.assertDictEqual({'id': 1, 'char': 'a', 'is_a': True},
                             self.dao.get(1))

    def test_get_fail(self):
        assert self.dao.get(42) is None

    def test_filtered_get_success(self):
        object_2 = self.dao.get(2)
        assert self.dao.filter(pred_not_a).get(2) == object_2

    def test_filtered_get_fail(self):
        self.assertIsNone(self.dao.filter(pred_not_a).get(1))

    # QueryChain.one
    def test_query_chain_one(self):
        data = self.dao.filter(pred_a).one()
        self.assertDictEqual(data, {'id': 1, 'char': 'a', 'is_a': True})

        with self.assertRaises(exc.NoResultFound):
            data = self.dao.filter(pred_z).one()

        with self.assertRaises(exc.MultipleResultsFound):
            data = self.dao.filter(pred_not_a).one()

    # QueryChain.one
    def test_query_chain_one_or_none(self):
        data = self.dao.filter(pred_a).one_or_none()
        self.assertDictEqual(data, {'id': 1, 'char': 'a', 'is_a': True})

        data = self.dao.filter(pred_z).one_or_none()
        self.assertIsNone(data)

        with self.assertRaises(exc.MultipleResultsFound):
            data = self.dao.filter(pred_not_a).one_or_none()

    # QueryChain.exists
    def test_exists_all_success(self):
        assert self.dao.all().exists()

    # def test_exists_empty_fail(self):
    #     self.dao.clear()
    #     assert not self.dao.all().exists()

    def test_exists_filtered_success(self):
        assert self.dao.filter(pred_c).exists()

    def test_exists_filtered_fail(self):
        assert not self.dao.filter(pred_z).exists()

    # QueryChain.count
    def test_count_all(self):
        assert self.dao.all().count() == 3

    def test_filtered_count(self):
        assert self.dao.filter(pred_not_a).count() == 2

    # QueryChain.update
    def test_update_all(self):
        ids = self.dao.all().update(char='z')
        assert ids == [1, 2, 3]
        self.assertListEqual([dict(dto) for dto in self.dao.all()], [
            {'id': 1, 'char': 'z', 'is_a': True},
            {'id': 2, 'char': 'z', 'is_a': False},
            {'id': 3, 'char': 'z', 'is_a': False},
        ])

    def test_update_filtered(self):
        ids = self.dao.filter(pred_not_a).update(char='z')
        assert ids == [2, 3]
        self.assertListEqual([dict(dto) for dto in self.dao.all()], [
            {'id': 1, 'char': 'a', 'is_a': True},
            {'id': 2, 'char': 'z', 'is_a': False},
            {'id': 3, 'char': 'z', 'is_a': False},
        ])

    def test_update_filtered_by_id(self):
        ids = self.dao.filter(pred_not_a).filter_by(id_=2).update(char='z')
        assert ids == [2]
        self.assertListEqual([dict(dto) for dto in self.dao.all()], [
            {'id': 1, 'char': 'a', 'is_a': True},
            {'id': 2, 'char': 'z', 'is_a': False},
            {'id': 3, 'char': 'c', 'is_a': False},
        ])

    def test_update_none(self):
        ids = self.dao.filter(pred_z).update(char='z')
        assert ids == []
        self.assertListEqual([dict(dto) for dto in self.dao.all()], [
            {'id': 1, 'char': 'a', 'is_a': True},
            {'id': 2, 'char': 'b', 'is_a': False},
            {'id': 3, 'char': 'c', 'is_a': False},
        ])

    # QueryChain.remove
    def test_remove_all_error(self):
        with self.assertRaises(exc.UnrestrictedRemove) as error_info:
            self.dao.all().remove()

    def test_remove_filtered(self):
        ids = self.dao.filter(pred_a).remove()
        self.assertEqual([1], ids)
        self.assertEqual([2, 3], get_ids(self.dao.all()))

    def test_remove_filtered_by_id(self):
        ids = self.dao.filter(pred_not_a).filter_by(id_=2).remove()
        assert ids == [2]
        assert get_ids(self.dao.all()) == [1, 3]

    def test_remove_none(self):
        ids = self.dao.filter(pred_z).remove()
        assert ids == []
        assert get_ids(self.dao.all()) == [1, 2, 3]

    # Dao.filter_by
    def test_dao_filter_by_success(self):
        self.assertListEqual([{'id': 3, 'char': 'c', 'is_a': False}], [dict(dto) for dto in self.dao.filter_by(id_=3)])

    def test_dao_filter_by_both_arguments_error(self):
        with self.assertRaises(exc.QueryError):
            assert self.dao.filter_by(id_=3, ids=[3, 5])

    def test_dao_filter_by_two_times_error(self):
        with self.assertRaises(exc.QueryError):
            assert self.dao.filter_by(id_=3).filter_by(id_=5)

    # Dao.insert
    def test_insert(self):
        id_ = self.dao.insert({'char': 'd', 'is_a': False})
        assert id_ == 4

    def test_insert_with_id(self):
        id_ = self.dao.insert({'char': 'd', 'is_a': False})
        assert id_ == 4

    def test_insert_id_already_exists(self):
        id_ = self.dao.insert({'char': 'd', 'is_a': False, 'id':4})
        with self.assertRaises(exc.IdAlreadyExists):
            id_ = self.dao.insert({'char': 'd', 'is_a': False, 'id':4})

    # Dao.batch_insert
    def test_batch_insert(self):
        batch = [{'char': 'd', 'is_a': False}, {'char': 'e', 'is_a': False}]
        result = self.dao.batch_insert(batch)
        self.assertEqual((4, 5), result)
        self.assertListEqual([{'char': 'd', 'is_a': False, 'id': 4}, {'char': 'e', 'is_a': False, 'id': 5}],
                             [dict(dto) for dto in self.dao.filter(where('id')>=4)])

    # Dao.clear
    # def test_clear(self):
    #     self.dao.clear()
    #     assert list(self.dao.all()) == []

    # reference update
    def test_get_twice(self):
        data1 = self.dao.get(1)
        data2 = self.dao.get(1)
        data1.update({'char': 'b'})
        self.assertNotEqual(data1['char'], data2['char'])
