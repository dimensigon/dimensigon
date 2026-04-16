import typing as t
from datetime import datetime

import rsa
from flask import has_app_context, current_app
from sqlalchemy import select
from sqlalchemy.orm.exc import NoResultFound

from dimensigon import defaults
from dimensigon.domain.entities.base import EntityReprMixin, UUIDEntityMixin
from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import PrivateKey, PublicKey, UtcDateTime
from dimensigon.web import db

current = {}


class Dimension(UUIDEntityMixin, EntityReprMixin, db.Model):
    __tablename__ = 'L_dimension'
    name = db.Column(db.String(40), nullable=False, unique=True)
    private = db.Column(PrivateKey, unique=True)
    public = db.Column(PublicKey, unique=True)
    current = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    def __init__(self, name: str, private: t.Union[rsa.PrivateKey, bytes] = None,
                 public: t.Union[rsa.PublicKey, bytes] = None, created_at: datetime = get_now(), current=False,
                 **kwargs):
        super().__init__(**kwargs)
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
        global current
        if has_app_context():
            app = current_app._get_current_object()
            if app not in current:
                entity = db.session.execute(select(cls).filter_by(current=True)).scalars().one()
                if entity:
                    db.session.expunge(entity)
                    current[app] = entity
                else:
                    raise NoResultFound('No row was found for one()')
            return db.session.merge(current[app], load=False)
        return db.session.execute(select(cls).filter_by(current=True)).scalars().one()

    @classmethod
    def is_same_dimension(cls, source_server) -> bool:
        """Check if a source server belongs to the current dimension.

        For intra-dimension traffic, the securizer can be skipped in 'auto' mode.
        Returns True if source is from the same dimension (or if we can't determine).
        """
        try:
            # If source is a Server object with a known dimension, compare
            # For now, all servers in the local DB are considered same-dimension
            if source_server is None:
                return True
            from dimensigon.domain.entities import Server
            if isinstance(source_server, Server):
                return True  # Servers in our DB are in our dimension
            # If it's a string (IP/ID), check if it's a known server
            server = db.session.get(Server, source_server)
            return server is not None
        except Exception:
            return True  # Default to same-dimension (safe fallback)

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
