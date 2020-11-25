from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Server, User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.web import create_app, db
from tests.base import TestCaseLockBypass


class TestLogResourceList(TestCaseLockBypass):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        db.create_all()
        s = Server('server', port=8000, me=True)
        db.session.add(s)

        self.user = User(name='user', active=False)
        db.session.add(self.user)

        db.session.commit()
        self.auth = HTTPBearerAuth(create_access_token(self.user.id))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

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
        resp = self.client.get(url_for('api_1_0.userlist') + f"?filter[user]=root",
                               headers=self.auth.header)
        db.session.refresh(root)
        self.assertListEqual([root.to_json()], resp.get_json())

    def test_post(self):
        new_user_json = {"user": 'root',
                         "password": "1234",
                         "email": 'root@dimensigon.com',
                         "name": "Root"
                         }

        resp = self.client.post(url_for('api_1_0.userlist'), headers=self.auth.header,
                                json=new_user_json)
        self.assertEqual(400, resp.status_code)

        new_user_json = {"user": 'root',
                         "password": "1234",
                         "email": 'root@dimensigon.com',
                         }

        resp = self.client.post(url_for('api_1_0.userlist'), headers=self.auth.header,
                                json=new_user_json)
        self.assertEqual(201, resp.status_code)
        user = User.query.get(resp.get_json().get('user_id'))
        self.assertEqual('root', user.user)
        self.assertEqual("root@dimensigon.com", user.email)
        self.assertIsNotNone(user._password)
        self.assertNotEqual('1234', user._password)
        self.assertTrue(user.active)


class TestUserResource(TestCaseLockBypass):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        s = Server('server', port=8000, me=True)
        db.session.add(s)
        self.user = User('user', active=False)
        db.session.add(self.user)
        db.session.commit()
        self.auth = HTTPBearerAuth(create_access_token(self.user.id))

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
