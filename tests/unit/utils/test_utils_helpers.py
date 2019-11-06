from unittest import TestCase

import rsa

from dm.utils.helpers import convert, encode, decode


class TestConvert(TestCase):
    def test_convert(self):
        d = {'param1': 'value1', 'param2': {'test': 'test_value', 'subparam1': {'level3': 3}}}

        o = convert(d)
        self.assertEqual(o.param2.subparam1.level3, 3)

        self.assertDictEqual(o.param2.subparam1, {'level3': 3})


class TestEncodeDecode(TestCase):

    def test_encode_with_str(self):
        pub_key, priv_key = rsa.newkeys(512)

        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg, key=pub_key)

        msg_decrypted = decode(cipher_text, cipher_token, priv_key)

        self.assertEqual(msg, msg_decrypted)

    def test_encode_with_dict(self):
        pub_key, priv_key = rsa.newkeys(512)

        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg=msg, key=pub_key)

        msg_decrypted = decode(cipher_text, cipher_token, priv_key)

        self.assertEqual(dict(msg=msg), msg_decrypted)

    def test_encode_with_str_no_key(self):
        pub_key = priv_key = None

        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg, key=pub_key)

        msg_decrypted = decode(cipher_text, cipher_token, priv_key)

        self.assertEqual(msg, msg_decrypted)

    def test_encode_with_dict_no_key(self):
        pub_key = priv_key = None

        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg=msg, key=pub_key)

        msg_decrypted = decode(cipher_text, cipher_token, priv_key)

        self.assertEqual(dict(msg=msg), msg_decrypted)

    def test_encode_with_str_no_key_as_parameter(self):
        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg)

        msg_decrypted = decode(cipher_text, cipher_token)

        self.assertEqual(msg, msg_decrypted)

    def test_encode_with_dict_no_key_as_parameter(self):
        msg = 'Hello World!'

        cipher_text, cipher_token = encode(msg=msg)

        msg_decrypted = decode(cipher_text, cipher_token)

        self.assertEqual(dict(msg=msg), msg_decrypted)