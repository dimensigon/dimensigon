from unittest import TestCase, mock

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

from dimensigon.domain.entities import Server, Scope, Locker, State
from dimensigon.web import db
from dimensigon.web.decorators import lock_catalog


class TestLockCatalog(TestCase):
    def setUp(self):
        """Create and configure a new self.app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the self.app with common test config

        self.app = Flask(__name__)
        self.app.config['JWT_SECRET_KEY'] = 'super-secret'

        self.jwt = JWTManager(self.app)

        @self.app.route('/', methods=['GET'])
        @jwt_required
        @lock_catalog
        def hello():
            return {'msg': 'default response'}

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.init_app(self.app)
        db.create_all()
        # self.d = generate_dimension('test')
        self.srv1 = Server(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='server1', me=True)
        Locker.set_initial()
        db.session.add(self.srv1)
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @mock.patch('dimensigon.web.decorators.lock_scope')
    def test_lock_catalog(self, mock_lock_scope):
        mock_lock_scope.return_value.__enter__.return_value = 1
        resp = self.client.get('/',
                               headers={"Authorization": f"Bearer {create_access_token(1)}"})

        self.assertEqual(200, resp.status_code)
        mock_lock_scope.assert_called_once_with(Scope.CATALOG)
        self.assertDictEqual({'msg': 'default response'}, resp.get_json())

    @mock.patch('dimensigon.web.decorators.get_servers_from_scope')
    @mock.patch('dimensigon.web.decorators.lock_scope')
    def test_lock_catalog_with_applicant(self, mock_lock_scope, mock_get_servers_from_scope):
        Locker.set_initial()
        l = Locker.query.get(Scope.CATALOG)
        l.state = State.LOCKED
        l.applicant = 2

        db.session.commit()

        mock_lock_scope.return_value.__enter__.return_value = 1
        mock_get_servers_from_scope.return_value = [self.srv1]
        resp = self.client.get('/',
                               headers={
                                   "Authorization": f"Bearer {create_access_token(1, user_claims={'applicant': 2})}"})

        self.assertEqual(200, resp.status_code)
        mock_lock_scope.assert_not_called()
        self.assertDictEqual({'msg': 'default response'}, resp.get_json())
