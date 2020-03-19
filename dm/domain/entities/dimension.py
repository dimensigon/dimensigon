import typing as t
import uuid
from datetime import datetime

import rsa

from dm import defaults
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

    @classmethod
    def get_current(cls) -> 'Dimension':
        return db.session.query(cls).filter_by(current=True).one_or_none()

    def to_json(self):
        return {'id': str(self.id) if self.id else None, 'name': self.name,
                'private': self.private.save_pkcs1().decode('ascii'),
                'public': self.public.save_pkcs1().decode('ascii'),
                'created_at': self.created_at.strftime(defaults.DATETIME_FORMAT)}

    @classmethod
    def from_json(cls, kwargs):
        return cls(id=kwargs.get('id'), name=kwargs.get('name'),
                   private=rsa.PrivateKey.load_pkcs1(kwargs.get('private')),
                   public=rsa.PublicKey.load_pkcs1(kwargs.get('public')),
                   created_at=datetime.strptime(kwargs.get('created_at'), defaults.DATETIME_FORMAT)
                   )
