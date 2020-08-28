import datetime as dt
import unittest

from dimensigon import defaults
from dimensigon.domain.entities.parameter import Parameter
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db


class TestParameter(unittest.TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_set_and_get(self):
        p = Parameter('data', dump=lambda x: x.strftime(defaults.DATETIME_FORMAT),
                            load=lambda x: dt.datetime.strptime(x, defaults.DATETIME_FORMAT))
        db.session.add(p)
        now = get_now()
        Parameter.set('data', now)

        p = Parameter.query.get('data')
        self.assertEqual(now.strftime(defaults.DATETIME_FORMAT), p.value)

        p = Parameter('integer', load=int, dump=str)
        db.session.add(p)
        Parameter.set('integer', 5)
        p = Parameter.query.get('integer')
        self.assertEqual('5', p.value)

        p = Parameter('name')
        db.session.add(p)
        Parameter.set('name', 'Joan')
        p = Parameter.query.get('name')
        self.assertEqual('Joan', p.value)


        # test get
        self.assertEqual(now, Parameter.get('data'))
        self.assertEqual(5, Parameter.get('integer'))
        self.assertEqual('Joan', Parameter.get('name'))

        p = Parameter('none')
        db.session.add(p)

        self.assertIsNone(Parameter.get('none'))
        self.assertEqual('default', Parameter.get('none', 'default'))