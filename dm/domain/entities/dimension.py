import uuid
from datetime import datetime

import uuid
from datetime import datetime

import rsa

from dm.domain.entities.base import EntityWithId
from dm.utils.typos import PrivateKey, PublicKey
from dm.web import db


class Dimension(EntityWithId):
    name = db.Column(db.String(40), nullable=False, unique=True)
    private = db.Column(PrivateKey, unique=True)
    public = db.Column(PublicKey, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, name: str, private: rsa.PrivateKey = None, public: rsa.PublicKey = None,
                 created_at: datetime = datetime.now(), id: uuid.UUID = None):
        self.id = id
        self.name = name
        self.private = private
        self.public = public
        self.created_at = created_at
