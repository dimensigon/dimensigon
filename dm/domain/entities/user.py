import uuid
from datetime import datetime

from passlib.hash import sha512_crypt

from dm.framework.domain import Entity, Id
from dm.utils.datamark import data_mark


class User(Entity):
    __id__ = Id(factory=uuid.uuid1)
    hash = sha512_crypt

    @data_mark
    def __init__(self, username, password=None, created_on=None, **kwargs):
        super().__init__(**kwargs)
        self.username = username
        self.password = password
        self.created_on = created_on or datetime.now()

    def hash_password(self, password):
        self.password = self.hash.hash(password)

    def verify_password(self, password):
        return self.hash.verify(password, self.password)
