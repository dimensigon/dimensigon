from unittest import TestCase

import werkzeug

from dm.domain.entities import Server
from dm.web import create_app, db


class TestBaseQuery(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')

    def test_get_or_404(self):
        with self.app.app_context():
            db.create_all()
            with self.assertRaises(werkzeug.exceptions.NotFound) as cm:
                Server.query.get_or_404(1)

            self.assertEqual(cm.exception.description, {'error': "Server id '1' not found"})
            self.assertEqual(cm.exception.code, 404)

    def test_first_or_404(self):
        with self.app.app_context():
            db.create_all()
            with self.assertRaises(werkzeug.exceptions.NotFound) as cm:
                Server.query.first_or_404()

            self.assertEqual(cm.exception.description, {'error': "No data in Server collection"})
            self.assertEqual(cm.exception.code, 404)
