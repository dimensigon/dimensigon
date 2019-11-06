import datetime
import uuid

import rsa

from framework.domain import Entity, Id


class Dimension(Entity):
    __id__ = Id(factory=uuid.uuid1)

    def __init__(self, name: str, priv: rsa.PrivateKey, pub: rsa.PublicKey, created: datetime.datetime, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.priv = priv
        self.pub = pub
        self.created = created
