from unittest import TestCase

from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import Server, File, FileServerAssociation
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.web import create_app, db, errors


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
        # set_initial(server=False)

        self.srv1 = Server('node1', id='00000000-0000-0000-0000-000000000001', me=True)
        self.file = File(source_server=self.srv1, target='/etc/ssh/sshd_config', id='00000000-0000-0000-0000-000000000002')
        self.fsa = FileServerAssociation(file=self.file, destination_server=self.srv1)

        db.session.add_all([self.srv1, self.file, self.fsa])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_to_from_json(self):
        fsa_json = self.fsa.to_json()
        fsa_json['dest_folder'] = '/new_target'

        smashed = FileServerAssociation.from_json(fsa_json)

        self.assertEqual(self.fsa.file, smashed.file)
        self.assertIsNotNone(smashed.file)
        self.assertEqual("/new_target", smashed.dest_folder)
        self.assertEqual(self.srv1, smashed.destination_server)
        self.assertIsNotNone(smashed.destination_server)
        self.assertEqual(self.fsa.last_modified_at, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)

        db.session.commit()
        db.session.close()

        del smashed

        fsa = FileServerAssociation.query.get(('00000000-0000-0000-0000-000000000002', self.srv1.id))
        self.assertEqual("/new_target", fsa.dest_folder)

    def test_from_json_new(self):
        fsa_json = dict(file_id=self.file.id,
                        dst_server_id=self.srv1.id,
                        dest_folder='/root',
                        last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))

        smashed = FileServerAssociation.from_json(fsa_json)

        self.assertEqual(self.fsa.file, smashed.file)
        self.assertIsNotNone(smashed.file)
        self.assertEqual("/root", smashed.dest_folder)
        self.assertEqual(self.srv1, smashed.destination_server)
        self.assertIsNotNone(smashed.destination_server)
        self.assertEqual(defaults.INITIAL_DATEMARK, smashed.last_modified_at)
        self.assertIsNotNone(smashed.last_modified_at)

        with self.assertRaises(errors.EntityNotFound):
            fsa_json = dict(file_id='unknown',
                            dst_server_id=self.srv1.id,
                            dest_folder='/root',
                            last_modified_at=defaults.INITIAL_DATEMARK.strftime(defaults.DATEMARK_FORMAT))

            FileServerAssociation.from_json(fsa_json)