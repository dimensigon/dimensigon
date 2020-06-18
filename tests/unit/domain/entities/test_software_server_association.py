from unittest import TestCase

from flask_jwt_extended import create_access_token

from dm import defaults
from dm.domain.entities import Server, Software, SoftwareServerAssociation
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {create_access_token('00000000-0000-0000-0000-000000000001')}"}

        db.create_all()
        set_initial()

        self.soft = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='test', version='1',
                             filename='file')
        self.soft2 = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa2', name='test', version='2',
                              filename='file')
        self.ssa = SoftwareServerAssociation(software=self.soft, server=Server.get_current(), path='/root')
        db.session.add_all([self.soft, self.soft2, self.ssa])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        ssa_json = self.ssa.to_json()
        ssa_json['path'] = '/new_root'

        smashed = SoftwareServerAssociation.from_json(ssa_json)

        self.assertEqual("/new_root", smashed.path)
        self.assertIsNotNone(smashed.path)
        self.assertEqual(Server.get_current(), smashed.server)
        self.assertIsNotNone(smashed.server)
        self.assertEqual(self.soft, smashed.software)
        self.assertIsNotNone(smashed.software)
        self.assertEqual(self.ssa.last_modified_at, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)

        db.session.commit()

        del smashed

        ssa = SoftwareServerAssociation.query.get(('aaaaaaaa-1234-5678-1234-56781234aaa1', Server.get_current().id))
        self.assertEqual("/new_root", ssa.path)

    def test_from_json_new(self):
        ssa_json = dict(software_id='aaaaaaaa-1234-5678-1234-56781234aaa2',
                        server_id=str(Server.get_current().id),
                        path='/root',
                        last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))

        smashed = SoftwareServerAssociation.from_json(ssa_json)

        self.assertEqual(defaults.INITIAL_DATEMARK, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)
        self.assertEqual("/root", smashed.path)
        self.assertIsNotNone(smashed.path)
        self.assertEqual(Server.get_current(), smashed.server)
        self.assertIsNotNone(smashed.server)
        self.assertEqual(self.soft2, smashed.software)
        self.assertIsNotNone(smashed.software)
