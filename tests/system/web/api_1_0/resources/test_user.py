from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import db, errors
from tests.base import TestResourceBase


class TestUserResourceList(TestResourceBase):

    def setUp(self) -> None:
        self.initials = dict(self.initials)
        self.initials.update(user=False)
        super().setUp()

    def fill_database(self):
        self.user = User(name='user', active=False)
        db.session.add(self.user)

    @property
    def auth(self):
        return HTTPBearerAuth(create_access_token(self.user.id))

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.userlist'), headers=self.auth.header)
        self.assertListEqual([self.user.to_json()], resp.get_json())

        root = User('root')
        db.session.add(root)
        db.session.commit()

        # test with filter
        resp = self.client.get(url_for('api_1_0.userlist') + "?filter[active]=True",
                               headers=self.auth.header)
        self.assertListEqual([root.to_json()], resp.get_json())

        # test with filter on a server
        resp = self.client.get(url_for('api_1_0.userlist') + f"?filter[name]=root",
                               headers=self.auth.header)
        db.session.refresh(root)
        self.assertListEqual([root.to_json()], resp.get_json())

    def test_post(self):
        new_user_json = {"name": 'root',
                         "password": "1234",
                         "email": 'root@dimensigon.com',
                         }

        resp = self.client.post(url_for('api_1_0.userlist'), headers=self.auth.header,
                                json=new_user_json)
        self.assertEqual(201, resp.status_code)
        user = User.query.get(resp.get_json().get('id'))
        self.assertEqual('root', user.name)
        self.assertEqual("root@dimensigon.com", user.email)
        self.assertIsNotNone(user._password)
        self.assertNotEqual('1234', user._password)
        self.assertTrue(user.active)

    def test_post_user_already_exists(self):
        root = User('root')
        db.session.add(root)
        db.session.commit()

        new_user_json = {"name": 'root',
                         "password": "1234",
                         "email": 'root@dimensigon.com',
                         }

        resp = self.client.post(url_for('api_1_0.userlist'), headers=self.auth.header,
                                json=new_user_json)
        self.validate_error_response(resp, errors.EntityAlreadyExists('User', 'root', ['name']))


class TestUserResource(TestResourceBase):

    def setUp(self) -> None:
        self.initials = dict(self.initials)
        self.initials.update(user=False)
        super().setUp()

    def fill_database(self):
        self.user = User('user', active=False)
        db.session.add(self.user)

    @property
    def auth(self):
        return HTTPBearerAuth(create_access_token(self.user.id))

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        self.assertEqual(self.user.to_json(), resp.get_json())

        resp = self.client.get(url_for('api_1_0.userresource', user_id='aaaa'), headers=self.auth.header)
        self.assertEqual(404, resp.status_code)

    def test_patch(self):
        patch_user_json = {"name": "Kevin"}

        resp = self.client.patch(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header,
                                 json=patch_user_json)
        self.assertEqual(400, resp.status_code)
        db.session.refresh(self.user)

        patch_user_json = {"email": "root@dimensigon.com"}

        self.assertIsNone(self.user.email)
        resp = self.client.patch(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header,
                                 json=patch_user_json)
        self.assertEqual(204, resp.status_code)
        db.session.refresh(self.user)
        self.assertEqual('root@dimensigon.com', self.user.email)

        resp = self.client.patch(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header,
                                 json=patch_user_json)
        self.assertEqual(202, resp.status_code)

    # def test_delete(self):
    #     resp = self.client.delete(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header)
    #     self.assertEqual(204, resp.status_code)
    #
    #     self.assertEqual(0, User.query.count())
    #
    #     resp = self.client.delete(url_for('api_1_0.userresource', user_id=str(self.user.id)), headers=self.auth.header)
    #     self.assertEqual(404, resp.status_code)
