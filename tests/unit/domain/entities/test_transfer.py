import threading
from unittest import TestCase

from dimensigon import defaults
from dimensigon.domain.entities import Server, Dimension, Software, Transfer, TransferStatus
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db
from tests.base import OneNodeMixin, TestDimensigonBase


class TestTransfer(TestDimensigonBase):


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

    def test_to_json(self):
        d = get_now()
        s = Software(id='aaaaaaaa-1234-5678-1234-56781234aaa1', name='test', version='1', filename='file')
        t = Transfer(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software=s, dest_path='/folder', num_chunks=0,
                     created_on=d)

        self.assertDictEqual(
            dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software_id='aaaaaaaa-1234-5678-1234-56781234aaa1',
                 dest_path='/folder', num_chunks=0, file='/folder/file',
                 status='WAITING_CHUNKS', created_on=d.strftime(defaults.DATETIME_FORMAT)),
            t.to_json())

        t = Transfer(id='aaaaaaaa-1234-5678-1234-56781234aaa2', software='filename', size=10, checksum='abc12',
                     dest_path='/folder', num_chunks=0, created_on=d)

        self.assertDictEqual(
            dict(id='aaaaaaaa-1234-5678-1234-56781234aaa2', size=10, checksum='abc12',
                 dest_path='/folder', num_chunks=0, file='/folder/filename',
                 status='WAITING_CHUNKS', created_on=d.strftime(defaults.DATETIME_FORMAT)),
            t.to_json())
