import typing as t
import uuid
from datetime import datetime

import rsa

from dm.domain.entities.base import EntityReprMixin
from dm.utils.typos import PrivateKey, PublicKey, UUID
from dm.web import db


class Dimension(db.Model, EntityReprMixin):
    __tablename__ = 'L_dimension'
    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(40), nullable=False, unique=True)
    private = db.Column(PrivateKey, unique=True)
    public = db.Column(PublicKey, unique=True)
    current = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, name: str, private: t.Union[rsa.PrivateKey, bytes] = None,
                 public: t.Union[rsa.PublicKey, bytes] = None,
                 created_at: datetime = datetime.now(), id: uuid.UUID = None, current=False):
        self.id = id
        self.name = name
        if isinstance(private, bytes):
            self.private = rsa.PrivateKey.load_pkcs1(private)
        else:
            self.private = private
        if isinstance(public, bytes):
            self.public = rsa.PublicKey.load_pkcs1(public)
        else:
            self.public = public
        self.created_at = created_at
        self.current = current

    @staticmethod
    def get_current() -> 'Dimension':
        return Dimension.query.filter_by(current=True).one_or_none()

    def to_json(self):
        return {'id': str(self.id), 'name': self.name, 'private': self.private.save_pkcs1().decode('ascii'),
                'public': self.public.save_pkcs1().decode('ascii'), 'created_at': self.created_at}
