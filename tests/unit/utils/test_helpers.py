import os
from unittest import TestCase
from unittest.mock import patch

import rsa
from cryptography.fernet import Fernet

from dm.utils.helpers import encrypt, decrypt, convert


class TestEncrypt(TestCase):

    def setUp(self) -> None:
        self.iv = os.urandom(16)
        self.time = 1574952157
        self.symmetric_key = Fernet.generate_key()

    @patch('cryptography.fernet.time.time')
    @patch('cryptography.fernet.os.urandom')
    @patch('dm.utils.helpers.Fernet.generate_key')
    def test_encrypt(self, mocked_generate_key, mocked_urandom, mocked_time):
        mocked_generate_key.return_value = self.symmetric_key
        mocked_urandom.return_value = self.iv
        mocked_time.return_value = self.time
        symmetric_key = Fernet.generate_key()
        cipher_suite = Fernet(symmetric_key)
        data = b'private message. You should not read this!'
        cipher_data = cipher_suite.encrypt(data)

        with patch('dm.utils.helpers.Fernet.generate_key') as mocked_generate_key:
            mocked_generate_key.return_value = symmetric_key
            ea = encrypt(data)
            self.assertTupleEqual((cipher_data, symmetric_key), ea)

            ea = encrypt(data, symmetric_key=symmetric_key)
            self.assertTupleEqual((cipher_data, None), ea)


class TestDecrypt(TestCase):

    def setUp(self) -> None:
        self.symmetric_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.symmetric_key)
        self.data = b'private message. You should not read this!'
        self.cipher_data = self.cipher_suite.encrypt(self.data)

    def test_decrypt(self):
        da = decrypt(self.cipher_data, self.symmetric_key)
        self.assertEqual(self.data, da)


class TestConvert(TestCase):
    def test_convert(self):
        d = {'param1': 'value1', 'param2': {'test': 'test_value', 'subparam1': {'level3': 3}}}

        o = convert(d)
        self.assertEqual(o.param2.subparam1.level3, 3)

        self.assertDictEqual(o.param2.subparam1, {'level3': 3})
