from datetime import datetime
import uuid

import rsa

from dm.utils.typos import UUID, PrivateKey, PublicKey
from dm.web import db


class Dimension(db.Model):
    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(40), nullable=False, unique=True)
    private = db.Column(PrivateKey, unique=True)
    public = db.Column(PublicKey, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, name: str, private: rsa.PrivateKey = None, public: rsa.PublicKey = None,
                 created_at: datetime = datetime.now()):
        self.name = name
        self.private = private
        self.public = public
        self.created_at = created_at

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.id}>'
