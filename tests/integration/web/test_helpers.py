from unittest import TestCase

from dimensigon.domain.entities import Server
from dimensigon.web import create_app, db
from dimensigon.web import errors


class TestBaseQuery(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')

    def test_get_or_raise(self):
        with self.app.app_context():
            db.create_all()
            with self.assertRaises(errors.EntityNotFound) as cm:
                Server.query.get_or_raise(1)

            self.assertTupleEqual(cm.exception.args, ("Server", 1))

    def test_first_or_raise(self):
        with self.app.app_context():
            db.create_all()
            with self.assertRaises(errors.NoDataFound) as cm:
                Server.query.first_or_raise()

            self.assertEqual(cm.exception.args, ("Server",))
