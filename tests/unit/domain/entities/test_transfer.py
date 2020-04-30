import threading
from datetime import datetime
from unittest import TestCase

from dm import defaults
from dm.domain.entities import Server, Dimension, Software, Transfer, TransferStatus
from dm.web import create_app, db


class TestTransfer(TestCase):
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

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_wait_transfer(self):
        s = Software(name='test', version='1', filename='file')
        t = Transfer(software=s, dest_path='', num_chunks=0)

        db.session.add_all([s, t])
        db.session.commit()

        status = t.wait_transfer(timeout=0.1, refresh_interval=0.01)
        self.assertEqual(TransferStatus.WAITING_CHUNKS, status)

        def update_transfer(app, transfer_id):
            with app.app_context():
                tr = Transfer.query.get(transfer_id)
                tr.status = TransferStatus.COMPLETED
                db.session.commit()

        th = threading.Timer(0.05, update_transfer, (self.app, t.id))
        th.start()
        status = t.wait_transfer(timeout=0.1, refresh_interval=0.01)
        self.assertEqual(TransferStatus.COMPLETED, status)

    def test_json(self):
        d = datetime.now()
        s = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='test', version='1', filename='file')
        t = Transfer(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software=s, dest_path='', num_chunks=0, created_on=d)

        self.assertDictEqual(
            dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software_id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                 dest_path='', num_chunks=0,
                 status='WAITING_CHUNKS', created_on=d.strftime(defaults.DATETIME_FORMAT)),
            t.to_json())

        t = Transfer(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software='filename', size=10, checksum='abc12',
                     dest_path='', num_chunks=0, created_on=d)

        self.assertDictEqual(
            dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', filename='filename', size=10, checksum='abc12',
                 dest_path='', num_chunks=0,
                 status='WAITING_CHUNKS', created_on=d.strftime(defaults.DATETIME_FORMAT)),
            t.to_json())
