from unittest import TestCase
from unittest.mock import patch

import rsa

from dm.utils.helpers import convert, update_config_yaml


class TestConvert(TestCase):

    def test_convert(self):
        d = {'param1': 'value1', 'param2': {'test': 'test_value', 'subparam1': {'level3': 3}}}

        o = convert(d)
        self.assertEqual(o.param2.subparam1.level3, 3)

        self.assertDictEqual(o.param2.subparam1, {'level3': 3})

    @patch('dm.utils.helpers.save_config_yaml')
    @patch('dm.utils.helpers.load_config_yaml')
    def test_update_config_yaml(self, mocked_load, mocked_save):
        mocked_load.return_value = {'dm': {'port': 80, 'host': '0.0.0.0'}, 'elevator': True}
        update_config_yaml('dm', {'port': 5000, 'host': '127.0.0.1'})
        mocked_save.assert_called_with({'dm': {'port': 5000, 'host': '127.0.0.1'}, 'elevator': True}, 'config.yaml')

        mocked_load.return_value = {'dm': {'port': 80, 'host': '0.0.0.0'}, 'elevator': True}
        update_config_yaml('dm.port', 5000)
        mocked_save.assert_called_with({'dm': {'port': 5000, 'host': '0.0.0.0'}, 'elevator': True}, 'config.yaml')

