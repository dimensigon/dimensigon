import datetime as dt
import os
from unittest import TestCase, mock

from dimensigon.domain.entities import bypass_datamark_update, catalog, Orchestration, Catalog, Server, Route
from dimensigon.web import db, create_app

basedir = os.path.abspath(os.path.dirname(__file__))


class TestInit(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app.config['SECURIZER'] = False
        # user sqlite in a file as flush does not emits states in an inmemory database
        # self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+os.path.join(basedir, 'test.db')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # def remove_db():
        #     try:
        #         os.remove(os.path.join(basedir, 'test.db'))
        #     except FileNotFoundError:
        #         pass
        #
        # self.addCleanup(remove_db)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_bypass_datamark_update(self):
        self.assertTrue(getattr(catalog, 'datemark', True))
        with bypass_datamark_update():
            self.assertFalse(catalog.datemark)
        self.assertTrue(catalog.datemark)

    @mock.patch('dimensigon.domain.entities.get_now')
    def test_sqlalchemy_entity_events(self, mock_now):
        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)

        o = Orchestration('orch', 1, last_modified_at=dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), o.last_modified_at)
        db.session.add(o)
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), o.last_modified_at)
        db.session.commit()
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), o.last_modified_at)

        c = Catalog.query.get('Orchestration')
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), c.last_modified_at)

        mock_now.return_value = dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc)

        o.name = 'modified'
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), o.last_modified_at)
        db.session.flush()
        self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), o.last_modified_at)
        db.session.commit()
        self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), o.last_modified_at)

        c = Catalog.query.get('Orchestration')
        self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), c.last_modified_at)

        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        o2 = Orchestration('orch', 2, last_modified_at=dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc))
        db.session.add(o2)
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), o2.last_modified_at)

        with bypass_datamark_update():
            self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), o2.last_modified_at)

            o3 = Orchestration('orch', 3, last_modified_at=dt.datetime(2019, 4, 4, tzinfo=dt.timezone.utc))
            db.session.add(o3)
            o.name = 'orch'

            self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), o.last_modified_at)
            self.assertEqual(dt.datetime(2019, 4, 4, tzinfo=dt.timezone.utc), o3.last_modified_at)

        self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), o.last_modified_at)
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), o2.last_modified_at)
        self.assertEqual(dt.datetime(2019, 4, 4, tzinfo=dt.timezone.utc), o3.last_modified_at)
        db.session.commit()
        self.assertEqual(dt.datetime(2019, 4, 3, tzinfo=dt.timezone.utc), o.last_modified_at)
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), o2.last_modified_at)
        self.assertEqual(dt.datetime(2019, 4, 4, tzinfo=dt.timezone.utc), o3.last_modified_at)

        c = Catalog.query.get('Orchestration')
        self.assertEqual(dt.datetime(2019, 4, 4, tzinfo=dt.timezone.utc), c.last_modified_at)

    @mock.patch('dimensigon.domain.entities.get_now')
    def test_sqlalchemy_entity_events_server(self, mock_now):
        mock_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        s = Server('source', port=5000)
        d = Server('destination', port=5000)
        db.session.add_all([s, d])
        db.session.commit()

        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)

        s.route = Route(destination=d, proxy_server_or_gate=d.gates[0], cost=0)
        db.session.commit()
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), s.last_modified_at)

        g = s.add_new_gate(dns_or_ip='dns', port=5000)
        db.session.add(g)
        db.session.commit()
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), s.last_modified_at)
