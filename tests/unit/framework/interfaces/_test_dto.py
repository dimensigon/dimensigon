from unittest import TestCase

from dm.framework.interfaces.dao import Dto


class TestDto(TestCase):

    def test_dto(self):
        dto = Dto({'name': 'Les Montses'})
        dto.__id__ = 1
        dto2 = Dto(dto)
        self.assertEqual(1, dto2.id)
        self.assertIsInstance(dto2, (dict, Dto))
        # noinspection PyArgumentList
        dto3 = Dto(**dto)

        self.assertIsNone(dto3.id)

    def test_dto_with_id(self):
        dto = Dto({'name': 'Les Montses', 'id': 17})
        self.assertEqual(17, dto.__id__)
        self.assertNotIn('id', dto)

        dto = Dto({'name': 'Les Montses', 'id_': 17})
        self.assertEqual(17, dto.__id__)
        self.assertNotIn('id_', dto)

        dto = Dto(**{'name': 'Les Montses', 'id': 17})
        self.assertEqual(17, dto.__id__)
        self.assertNotIn('id', dto)

        dto = Dto(**{'name': 'Les Montses', 'id_': 17})
        self.assertEqual(17, dto.__id__)
        self.assertNotIn('id_', dto)

    def test_to_dict(self):
        dto = Dto({'name': 'Les Montses', 'components': 4, 'id': 17})
        self.assertDictEqual({'name': 'Les Montses', 'components': 4}, dto)
        self.assertDictEqual({'name': 'Les Montses', 'components': 4, 'id': 17}, dto.to_dict())

        self.assertDictEqual({'id': 17, 'name': 'Les Montses', 'components': 4},
                             dto.to_dict(dump_only=('name', 'components')))
        self.assertDictEqual({'id': 17, 'name': 'Les Montses'}, dto.to_dict(exclude_only=('components',)))
