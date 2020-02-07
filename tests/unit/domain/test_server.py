from unittest import TestCase
from unittest.mock import patch

from dm.domain.entities import Server, Dimension
from dm.web import create_app, db


class TestServer(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Server.set_initial()
        d = Dimension(name='test', current=True)
        db.session.add(d)
        db.session.commit()
        self.client = self.app.test_client(use_cookies=True)
        self.n1 = Server(name='n1', ip='127.0.0.1', gateway=None, cost=0)
        self.n2 = Server(name='n2', ip='127.0.0.2', dns_name='n2', gateway=None, cost=0)
        self.r1 = Server(name='r1', ip='127.0.1.1', gateway=self.n1, cost=1)
        self.r2 = Server(name='r1', ip='127.0.1.1', dns_name='r2', gateway=self.n2, cost=1)
        db.session.add_all([self.n1, self.n2, self.r1, self.r2])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.domain.entities.server.url_for')
    def test_url(self, mock_url):
        self.assertEqual('http://127.0.0.1:5000', self.n1.url())
        self.assertEqual('http://n2:5000', self.n2.url())
        self.assertEqual('http://127.0.0.1:5000', self.r1.url())
        self.assertEqual('http://n2:5000', self.r2.url())

        mock_url.return_value = '/'

        self.assertEqual('http://127.0.0.1:5000/', self.n1.url('api'))

        mock_url.assert_called_once_with('api')

    def test_get_neighbours(self):
        self.fail()

    def test_get_not_neighbours(self):
        self.fail()

    def test_get_current(self):
        self.fail()
