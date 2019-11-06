import datetime
from unittest import TestCase, mock
# function to mock the time
from unittest.mock import call

from dm.domain.entities.catalog import Catalog
from dm.domain.exceptions import CatalogError
from dm.framework.domain import Entity



def get_now(**kwargs):
    return datetime.datetime(2012, 1, 1, 10, 10, 10, 0) + datetime.timedelta(**kwargs)


class TestCatalog(TestCase):
    def test_generate_data_mark(self):
        with mock.patch('dm.domain.catalog_manager.get_now', side_effect=get_now):
            from dm.domain.catalog_manager import CatalogManager
            self.assertEqual(20120101101010000000, CatalogManager(int).generate_data_mark())

            self.assertEqual('20120101101010000000', CatalogManager(str).generate_data_mark())

            self.assertEqual(datetime.datetime(2012, 1, 1, 10, 10, 10, 0),
                             CatalogManager(datetime.datetime).generate_data_mark())

    @mock.patch('dm.domain.catalog_manager.CatalogManager.generate_data_mark')
    def test_set_data_mark_int(self, mocked_generate_datamark):
        from dm.domain.catalog_manager import CatalogManager
        c = CatalogManager(int)

        A = type("A", (), {'datamark': None})
        B = type("B", (), {})
        aa = A()
        bb = B()

        mocked_generate_datamark.return_value = 2
        c.set_data_mark(aa)
        mocked_generate_datamark.return_value = 3
        c.set_data_mark(bb)

        self.assertEqual(2, aa.data_mark)
        self.assertEqual(3, bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual([2, 3], c._data_mark)

        mocked_generate_datamark.return_value = 1
        aa.data_mark = None
        c.set_data_mark(aa)

        self.assertEqual(1, aa.data_mark)
        self.assertEqual(3, bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual([2, 3], c._data_mark)

        mocked_generate_datamark.return_value = 3
        c.set_data_mark(aa)

        self.assertEqual(1, aa.data_mark)
        self.assertEqual(3, bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual([2, 3], c._data_mark)

        aa.data_mark = 4
        c.set_data_mark(aa)

        self.assertEqual(4, aa.data_mark)
        self.assertEqual(3, bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual([4, 3], c._data_mark)

        self.assertEqual(4, c.max_data_mark)

    @mock.patch('dm.domain.catalog_manager.CatalogManager.generate_data_mark')
    def test_set_data_mark_force(self, mocked_generate_datamark):
        from dm.domain.catalog_manager import CatalogManager
        c = CatalogManager(str)

        A = type("A", (), {'data_mark': None})
        B = type("B", (), {})
        aa = A()
        bb = B()

        mocked_generate_datamark.return_value = '2'
        c.set_data_mark(aa)
        mocked_generate_datamark.return_value = '3'
        c.set_data_mark(bb)

        self.assertEqual('2', aa.data_mark)
        self.assertEqual('3', bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual(['2', '3'], c._data_mark)

        mocked_generate_datamark.return_value = '1'
        aa.data_mark = None
        c.set_data_mark(aa, force=True)

        self.assertEqual('1', aa.data_mark)
        self.assertEqual('3', bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual(['2', '3'], c._data_mark)

        mocked_generate_datamark.return_value = '3'
        c.set_data_mark(aa, force=True)

        self.assertEqual('3', aa.data_mark)
        self.assertEqual('3', bb.data_mark)
        self.assertListEqual(['A', 'B'], c._entities)
        self.assertListEqual(['3', '3'], c._data_mark)

        self.assertEqual('3', c.max_data_mark)

    @mock.patch('dm.domain.catalog_manager.CatalogManager.generate_data_mark')
    def test_save_catalog(self, mocked_generate_datamark):
        from dm.domain.catalog_manager import CatalogManager
        get = mock.Mock()
        save = mock.Mock()
        c = CatalogManager(int)

        A = type("A", (Entity, ), {'data_mark': None})
        B = type("B", (Entity, ), {})
        C = type("C", (Entity, ), {})
        aa = A()
        bb = B()

        mocked_generate_datamark.return_value = 2
        c.set_data_mark(aa)
        self.assertListEqual(c._entities, ['A'])
        self.assertListEqual(c._data_mark, [2])

        mocked_generate_datamark.return_value = 2
        c.set_data_mark(bb)

        self.assertListEqual(c._entities, ['A', 'B'])
        self.assertListEqual(c._data_mark, [2, 2])

        with self.assertRaises(CatalogError):
            c.save_catalog()

        c.set_catalog(
            lambda: [Catalog(entity='B', data_mark=4), Catalog(entity='C', data_mark=1)],
            get,
            save)

        c.save_catalog()
        self.assertEqual(3, save.call_count)

        expected = [call(Catalog(entity='A', data_mark=2)),
                    call(Catalog(entity='B', data_mark=4)),
                    call(Catalog(entity='C', data_mark=1))]

        self.assertEqual(expected, save.call_args_list)
