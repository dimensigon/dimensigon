from flask import url_for

from dimensigon.domain.entities import Vault
from dimensigon.domain.entities.user import ROOT, JOIN
from dimensigon.web import db, errors
from tests.base import TestResourceBase


class TestVaultList(TestResourceBase):

    def setUp(self) -> None:
        super().setUp()

    def fill_database(self):
        self.vr1 = Vault(user_id=ROOT, scope='global', name='foo', value='bar')
        self.vr2 = Vault(user_id=ROOT, scope='test', name='foo', value='test_content')
        self.vj1 = Vault(user_id=JOIN, scope='global', name='bar', value='foo')
        self.vj2 = Vault(user_id=JOIN, scope='test2', name='bar', value='test_content')

        db.session.add_all([self.vr1, self.vr2, self.vj1, self.vj2])

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.vaultlist'), headers=self.auth.header)

        self.assertListEqual([self.vr1.to_json(no_delete=True),
                              self.vr2.to_json(no_delete=True)], resp.get_json())

        resp = self.client.get(url_for('api_1_0.vaultlist') + '?params=scopes', headers=self.auth.header)

        self.assertListEqual(['global', 'test'], resp.get_json())

        v = Vault(user_id=ROOT, scope='test', name='home', value='root')
        db.session.add(v)

        resp = self.client.get(url_for('api_1_0.vaultlist') + '?params=vars', headers=self.auth.header)

        self.assertListEqual(['foo', 'home'], resp.get_json())

        resp = self.client.get(url_for('api_1_0.vaultlist') + '?params=vars&scope=global', headers=self.auth.header)

        self.assertListEqual(['foo'], resp.get_json())

    def test_post(self):
        resp = self.client.post(url_for('api_1_0.vaultlist'), json={'name': 'new', 'value': 'bar'},
                                headers=self.auth.header)

        self.assertEqual(204, resp.status_code)
        v = Vault.query.get((ROOT, 'global', 'new'))
        self.assertEqual('bar', v.value)

        resp = self.client.post(url_for('api_1_0.vaultlist'), json={'name': 'new', 'value': 'bar'},
                                headers=self.auth.header)
        self.validate_error_response(resp, errors.EntityAlreadyExists("Vault", ['global', 'new'], ['scope', 'name']))


class TestVaultResource(TestResourceBase):
    def fill_database(self):
        self.vr1 = Vault(user_id=ROOT, scope='global', name='foo', value='bar')
        self.vr2 = Vault(user_id=ROOT, scope='test', name='foo', value='test_content')
        self.vj1 = Vault(user_id=JOIN, scope='global', name='bar', value='foo')
        self.vj2 = Vault(user_id=JOIN, scope='test', name='bar', value='test_content')

        db.session.add_all([self.vr1, self.vr2, self.vj1, self.vj2])

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.vaultresource', name='foo'), headers=self.auth.header)
        self.assertDictEqual(self.vr1.to_json(no_delete=True), resp.get_json())

        resp = self.client.get(url_for('api_1_0.vaultresource', name='foo', scope='test'), headers=self.auth.header)
        self.assertDictEqual(self.vr2.to_json(no_delete=True), resp.get_json())

        resp = self.client.get(url_for('api_1_0.vaultresource', name='foo') + '?params=human', headers=self.auth.header)
        self.assertDictEqual(self.vr1.to_json(no_delete=True, human=True), resp.get_json())

        resp = self.client.get(url_for('api_1_0.vaultresource', name='fake'), headers=self.auth.header)
        self.validate_error_response(resp, errors.EntityNotFound("Vault", [ROOT, 'global', 'fake']))

    def test_post(self):
        resp = self.client.post(url_for('api_1_0.vaultresource', name='foo'), json={'value': ['list']},
                                headers=self.auth.header)

        self.assertEqual(204, resp.status_code)
        v = Vault.query.get((ROOT, 'global', 'foo'))
        self.assertListEqual(['list'], v.value)

        resp = self.client.post(url_for('api_1_0.vaultresource', name='fake'), json={'value': ['list']},
                                headers=self.auth.header)
        self.validate_error_response(resp, errors.EntityNotFound("Vault", [ROOT, 'global', 'fake']))

    def test_put(self):
        resp = self.client.put(url_for('api_1_0.vaultresource', name='foo'), json={'value': ['list']},
                               headers=self.auth.header)

        self.assertEqual(204, resp.status_code)
        v = Vault.query.get((ROOT, 'global', 'foo'))
        self.assertListEqual(['list'], v.value)

        resp = self.client.put(url_for('api_1_0.vaultresource', name='fake'), json={'value': ['list']},
                               headers=self.auth.header)
        self.assertEqual(204, resp.status_code)
        v = Vault.query.get((ROOT, 'global', 'fake'))
        self.assertListEqual(['list'], v.value)
