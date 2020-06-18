import typing as t
from datetime import datetime

import rsa

from dm import defaults
from dm.domain.entities.base import EntityReprMixin, UUIDEntityMixin
from dm.utils.helpers import get_now
from dm.utils.typos import PrivateKey, PublicKey, UtcDateTime
from dm.web import db


class Dimension(db.Model, UUIDEntityMixin, EntityReprMixin):
    __tablename__ = 'L_dimension'
    name = db.Column(db.String(40), nullable=False, unique=True)
    private = db.Column(PrivateKey, unique=True)
    public = db.Column(PublicKey, unique=True)
    current = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    def __init__(self, name: str, private: t.Union[rsa.PrivateKey, bytes] = None,
                 public: t.Union[rsa.PublicKey, bytes] = None, created_at: datetime = get_now(), current=False,
                 **kwargs):
        UUIDEntityMixin.__init__(self, **kwargs)
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
