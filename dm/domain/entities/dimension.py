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

    def __init__(self, name: str, private: rsa.PrivateKey = None, public: rsa.PublicKey = None,
                 created_at: datetime = datetime.now(), id: uuid.UUID = None, current=False):
        self.id = id
        self.name = name
        self.private = private
        self.public = public
        self.created_at = created_at
        self.current = current

    @staticmethod
    def get_current() -> 'Dimension':
        return Dimension.query.filter_by(current=True).one_or_none()
