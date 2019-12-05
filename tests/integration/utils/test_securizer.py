import base64
import json
import os
import pickle
import time
from unittest import TestCase
import typing as t
from unittest.mock import patch, MagicMock, PropertyMock

import rsa
from cryptography.fernet import Fernet
from flask import Flask, request
from rsa import PublicKey, PrivateKey

from dm.utils.decorators import securizer

app = Flask('test')

data = 'Some Random Data'
dict_data = {'text': data}
dict_changed = {'text': 'Changed Text'}
error_dict = {'error': 'Some Random Error'}

@app.route('/get_securizer_text_data')
@securizer
def get_securizer_text_data():
    return data


@app.route('/get_securizer_dict_data')
@securizer
def get_securizer_dict_data():
    return dict_data, 202


@app.route('/post_securizer', methods=['POST'])
@securizer
def post_securizer_text_data():
    incoming = request.json
    if incoming.get('text') == data:
        incoming.update(dict_changed)
    return incoming, 202


@app.route('/post_securizer_error_dict', methods=['POST'])
@securizer
def post_securizer_error_dict():
    return error_dict, 404


@app.route('/post_securizer_dict_raise', methods=['POST'])
@securizer
def post_securizer_dict_raise():
    raise ValueError


def urandom(n):
    return b'\xb0\x18\xeb@\x1e\xd1\x9a\x0et@G\x11=\xc2\xad2\x98kk\xad\xf4\xacP\xd22\xb7\xa8\ta\x12~\xf0\xa8+\xc4\xf0\x9f\x9a\x04\xa6B!6\xa18\x1fo\x8e\xba\xf9\xc3[\xc0\x97\x8cW^y1\xd4\xb7\xb7\x9b\xea'[0:n]


class TestSecurizer(TestCase):

    @patch('rsa.pkcs1.os.urandom', side_effect=urandom)
    def setUp(self, mocked_urandom) -> None:
        self.pub = PublicKey(143782795986372720850220463737065781029235454142440572746046544148930363151763813347341745313915399123354990756669749076683013034885165119847786270351594842442981065358726983231315321564447571418267121310519323411121560778550699827881562946492797935006653854519631190709566218375530096701218112650405060167517, 65537)
        self.priv = PrivateKey(143782795986372720850220463737065781029235454142440572746046544148930363151763813347341745313915399123354990756669749076683013034885165119847786270351594842442981065358726983231315321564447571418267121310519323411121560778550699827881562946492797935006653854519631190709566218375530096701218112650405060167517, 65537, 69852151325360041795476896179630398129145789774343735533536413310920454588843066560355430200493650803187505541932162608183323191749832495397007270184696830768445123721830910202854777645277454795835908499707065401126097080846644758018385426779975714324155537147291195275362168693546875250580899876637841591813, 50115580011635745028903295475107483804171694074049326120674798681939605666587265090171490142682603477006887778504258729778165936215497607894264815858591629418165327, 2869023883450804928538249632456264787961161077879895522182508746139752991741797569667411498188980018750878332397749966501462837744017153285005971)
        self.symmetric_key = b'KjPxY2cbTXjl-S1pnEkVucYaYnK-ANRRa2onMalpM_8='
        self.cipher_suite = Fernet(self.symmetric_key)
        self.encrypted_key = rsa.encrypt(self.symmetric_key, self.pub)
        self.iv = b'\xa9\xbe#e\xe0\xf7\xceR4q\xee[8\xb5/\xef'
        self.time = 1574682425

        self.client = app.test_client()

    def pack_msg(self, msg, add_symm_key=True):
        dumped_msg = pickle.dumps(msg)
        encrypted_msg = self.cipher_suite.encrypt(dumped_msg)
        return_data = dict(data=base64.b64encode(encrypted_msg).decode('ascii'))
        return_data.update(key=base64.b64encode(self.encrypted_key).decode('ascii')) if add_symm_key else None
        signature = rsa.sign(json.dumps(return_data).encode('ascii'), self.priv, 'SHA-512')
        return_data.update(signature=base64.b64encode(signature).decode('ascii'))
        return return_data

    @patch('cryptography.fernet.os.urandom')
    def test_securizer_get_text(self, mocked_urandom):
        mocked_urandom.return_value = self.iv
        with app.app_context():
            with patch('dm.utils.decorators.dimension') as mocked_dimension:
                with patch('dm.utils.helpers.Fernet.generate_key') as mocked_generate_key:
                    mocked_generate_key.return_value = self.symmetric_key
                    type(mocked_dimension).pub = PropertyMock(return_value=None)
                    type(mocked_dimension).priv = PropertyMock(return_value=None)

                    resp = self.client.get('/get_securizer_text_data')

                    self.assertEqual(data, resp.get_data(as_text=True))
                    self.assertEqual(200, resp.status_code)

                    type(mocked_dimension).pub = PropertyMock(return_value=self.pub)
                    type(mocked_dimension).priv = PropertyMock(return_value=self.priv)

                    resp = self.client.get('/get_securizer_text_data')

                    self.assertEqual(data, resp.get_data(as_text=True))
                    self.assertEqual(200, resp.status_code)

    @patch('rsa.pkcs1.os.urandom', side_effect=urandom)
    @patch('cryptography.fernet.time.time')
    @patch('cryptography.fernet.os.urandom')
    def test_securizer_get_dict(self, mocked_urandom, mocked_time, mocked_rsa_urandom):
        mocked_urandom.return_value = self.iv
        mocked_time.return_value = self.time

        with app.app_context():
            with patch('dm.utils.decorators.dimension') as mocked_dimension:
                with patch('dm.utils.helpers.Fernet.generate_key') as mocked_generate_key:
                    mocked_generate_key.return_value = self.symmetric_key
                    type(mocked_dimension).pub = PropertyMock(return_value=None)
                    type(mocked_dimension).priv = PropertyMock(return_value=None)

                    resp = self.client.get('/get_securizer_dict_data')

                    expected_data = {'data': base64.b64encode(pickle.dumps(dict_data)).decode('ascii')}
                    self.assertEqual(expected_data, resp.get_json())
                    self.assertEqual(202, resp.status_code)

                    type(mocked_dimension).pub = PropertyMock(return_value=self.pub)
                    type(mocked_dimension).priv = PropertyMock(return_value=self.priv)

                    resp = self.client.get('/get_securizer_dict_data')

                    # Construct Response
                    expected_response = self.pack_msg(dict_data)

                    self.assertEqual(expected_response, resp.get_json())
                    self.assertEqual(202, resp.status_code)

    @patch('rsa.pkcs1.os.urandom', side_effect=urandom)
    @patch('cryptography.fernet.time.time')
    @patch('cryptography.fernet.os.urandom')
    def test_securizer_post(self, mocked_urandom, mocked_time, mocked_rsa_urandom):
        mocked_urandom.return_value = self.iv
        mocked_time.return_value = self.time

        with app.app_context():
            with patch('dm.utils.decorators.dimension') as mocked_dimension:
                with patch('dm.utils.helpers.Fernet.generate_key') as mocked_generate_key:
                    mocked_generate_key.return_value = self.symmetric_key
                    type(mocked_dimension).pub = PropertyMock(return_value=None)
                    type(mocked_dimension).priv = PropertyMock(return_value=None)

                    expected_data = {'data': base64.b64encode(pickle.dumps(dict_data)).decode('ascii')}

                    resp = self.client.post('/post_securizer', json=expected_data)

                    self.assertEqual({'data': base64.b64encode(pickle.dumps(dict_changed)).decode('ascii')}, resp.get_json())
                    self.assertEqual(202, resp.status_code)

                    type(mocked_dimension).pub = PropertyMock(return_value=self.pub)
                    type(mocked_dimension).priv = PropertyMock(return_value=self.priv)

                    expected_data = self.pack_msg(dict_data)
                    resp = self.client.post('/post_securizer', json=expected_data)

                    # Construct Response. we do not add symmetric key as it is already known
                    expected_response = self.pack_msg(dict_changed, add_symm_key=False)

                    self.assertEqual(expected_response, resp.get_json())
                    self.assertEqual(202, resp.status_code)

    @patch('rsa.pkcs1.os.urandom', side_effect=urandom)
    @patch('cryptography.fernet.time.time')
    @patch('cryptography.fernet.os.urandom')
    def test_securizer_post(self, mocked_urandom, mocked_time, mocked_rsa_urandom):
        mocked_urandom.return_value = self.iv
        mocked_time.return_value = self.time

        with app.app_context():
            with patch('dm.utils.decorators.dimension') as mocked_dimension:
                with patch('dm.utils.helpers.Fernet.generate_key') as mocked_generate_key:
                    mocked_generate_key.return_value = self.symmetric_key
                    type(mocked_dimension).pub = PropertyMock(return_value=None)
                    type(mocked_dimension).priv = PropertyMock(return_value=None)

                    expected_data = {'data': base64.b64encode(pickle.dumps(dict_data)).decode('ascii')}

                    resp = self.client.post('/post_securizer_error_dict', json=expected_data)

                    self.assertEqual(error_dict,
                                     resp.get_json())
                    self.assertEqual(404, resp.status_code)

                    type(mocked_dimension).pub = PropertyMock(return_value=self.pub)
                    type(mocked_dimension).priv = PropertyMock(return_value=self.priv)

                    expected_data = self.pack_msg(dict_data)
                    resp = self.client.post('/post_securizer_error_dict', json=expected_data)

                    self.assertEqual(error_dict, resp.get_json())
                    self.assertEqual(404, resp.status_code)

    @patch('rsa.pkcs1.os.urandom', side_effect=urandom)
    @patch('cryptography.fernet.time.time')
    @patch('cryptography.fernet.os.urandom')
    def test_securizer_post(self, mocked_urandom, mocked_time, mocked_rsa_urandom):
        mocked_urandom.return_value = self.iv
        mocked_time.return_value = self.time
