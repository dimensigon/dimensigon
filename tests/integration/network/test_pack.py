from collections import OrderedDict
from unittest import TestCase
from unittest.mock import patch

import rsa
from cryptography.fernet import Fernet

from dimensigon.network.encryptation import pack_msg, unpack_msg


class TestPack_msg_pickle(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.pub_key, cls.priv_key = rsa.newkeys(1024)
        cls.source = 'source'
        cls.dest = 'dest'
        cls.data = {'test': 'some random data', 'id': '11111111-2222-3333-4444-55555555abcd'}
        cls.sym_key = Fernet.generate_key()

    def test_pack_unpack_msg_with_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)

        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_msg = unpack_msg(packed_msg, self.pub_key, self.priv_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_msg_with_keys_change_dict_order(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)

        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        packed_msg = OrderedDict(packed_msg)
        ed = packed_msg.pop('enveloped_data')
        packed_msg['enveloped_data'] = ed
        unpacked_msg = unpack_msg(packed_msg, self.pub_key, self.priv_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_msg_without_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source)

        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertNotIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_data = unpack_msg(packed_msg)

        self.assertDictEqual(self.data, unpacked_data)

    def test_unpack_signature_error(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)

        packed_msg.update(source='changed')

        with self.assertRaises(rsa.pkcs1.VerificationError):
            unpack_msg(packed_msg, self.pub_key, self.priv_key)

    def test_pack_unpack_with_symmetric_key(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              symmetric_key=self.sym_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_force_key(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              symmetric_key=self.sym_key,
                              add_key=True)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_no_rsa_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, symmetric_key=self.sym_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertNotIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_encrypted(self):
        sym_key_encrypted = rsa.encrypt(self.sym_key, self.pub_key)
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              cipher_key=sym_key_encrypted)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key,
                                  cipher_key=sym_key_encrypted)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_error(self):
        sym_key_encrypted = rsa.encrypt(self.sym_key, self.pub_key)

        with self.assertRaises(ValueError) as e:
            pack_msg(self.data, self.dest, self.source, pub_key=self.pub_key, cipher_key=sym_key_encrypted)

    @patch('dimensigon.utils.helpers.Fernet.generate_key')
    def test_unpack_with_symmetric_key_as_parameter_and_cipher_in_msg(self, mocked_generate_key):
        mocked_generate_key.return_value = self.sym_key
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)


class TestPack_msg_json(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.pub_key, cls.priv_key = rsa.newkeys(1024)
        cls.source = 'source'
        cls.dest = 'dest'
        cls.data = {'test': 'some random data'}
        cls.sym_key = Fernet.generate_key()

    def test_pack_unpack_msg_with_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)

        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_msg = unpack_msg(packed_msg, self.pub_key, self.priv_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_msg_without_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source)

        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertNotIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_data = unpack_msg(packed_msg)

        self.assertDictEqual(self.data, unpacked_data)

    def test_unpack_signature_error(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)

        packed_msg.update(source='changed')

        with self.assertRaises(rsa.pkcs1.VerificationError):
            unpack_msg(packed_msg, self.pub_key, self.priv_key)

    def test_pack_unpack_with_symmetric_key(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              symmetric_key=self.sym_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_force_key(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              symmetric_key=self.sym_key,
                              add_key=True)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_no_rsa_keys(self):
        packed_msg = pack_msg(self.data, self.dest, self.source, symmetric_key=self.sym_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertNotIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_msg = unpack_msg(packed_msg, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_unpack_with_symmetric_key_encrypted(self):
        sym_key_encrypted = rsa.encrypt(self.sym_key, self.pub_key)
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key,
                              cipher_key=sym_key_encrypted)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key,
                                  cipher_key=sym_key_encrypted)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_pack_error(self):
        sym_key_encrypted = rsa.encrypt(self.sym_key, self.pub_key)

        with self.assertRaises(ValueError) as e:
            pack_msg(self.data, self.dest, self.source, pub_key=self.pub_key, cipher_key=sym_key_encrypted)

    @patch('dimensigon.utils.helpers.Fernet.generate_key')
    def test_unpack_with_symmetric_key_as_parameter_and_cipher_in_msg(self, mocked_generate_key):
        mocked_generate_key.return_value = self.sym_key
        sym_key_encrypted = rsa.encrypt(self.sym_key, self.pub_key)
        packed_msg = pack_msg(self.data, self.dest, self.source, self.pub_key, self.priv_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key, symmetric_key=self.sym_key)

        self.assertDictEqual(self.data, unpacked_msg)

    def test_unpack_without_data_and_keys(self):
        packed_msg = pack_msg({}, self.dest, self.source, self.pub_key, self.priv_key)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertIn('key', packed_msg)
        self.assertIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        with self.assertRaises(ValueError) as e:
            unpack_msg(packed_msg, symmetric_key=self.sym_key)

        unpacked_msg = unpack_msg(packed_msg, pub_key=self.pub_key, priv_key=self.priv_key, symmetric_key=self.sym_key)

        self.assertDictEqual({}, unpacked_msg)

    def test_unpack_without_data_and_without_keys(self):
        packed_msg = pack_msg({}, self.dest, self.source)
        self.assertIn('source', packed_msg)
        self.assertIn('destination', packed_msg)
        self.assertNotIn('key', packed_msg)
        self.assertNotIn('signature', packed_msg)
        self.assertIn('enveloped_data', packed_msg)

        unpacked_msg = unpack_msg(packed_msg)

        self.assertDictEqual({}, unpacked_msg)
