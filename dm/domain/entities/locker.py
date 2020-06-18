from enum import Enum

from dm.utils import typos
from dm.utils.typos import Pickle
from dm.web import db


class Scope(Enum):
    CATALOG = 1  # lock catalog for updating information
    ORCHESTRATION = 2  # execute an orchestration
    UPGRADE = 3  # upgrading Catalog from another server

    def __lt__(self, other):
        return self.value < other.value


class State(Enum):
    UNLOCKED = 1
    PREVENTING = 2
    LOCKED = 3


class Locker(db.Model):
    __tablename__ = 'L_locker'

    scope = db.Column(typos.Enum(Scope, name=True), primary_key=True)
    state = db.Column(typos.Enum(State), nullable=False)
    applicant = db.Column(Pickle)

    @classmethod
    def set_initial(cls):
        for scope in Scope:
            l = cls.query.get(scope)
            if not l:
                l = cls(scope=scope, state=State.UNLOCKED)
                db.session.add(l)
            else:
                if l.state != State.UNLOCKED:
                    l.state = State.UNLOCKED

    def __repr__(self):
        return f"Locker({self.scope.name}, {self.state.name})"

    def __str__(self):
        return f"Locker({self.scope.name}, {self.state.name})"
