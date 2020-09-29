from enum import Enum

from dimensigon.utils import typos
from dimensigon.utils.typos import Pickle
from dimensigon.web import db


class Scope(Enum):
    CATALOG = 1  # lock catalog for updating information
    UPGRADE = 2  # upgrading Catalog from another server
    ORCHESTRATION = 3  # execute an orchestration

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
    def set_initial(cls, session=None, unlock=False):
        if session is None:
            session = db.session

        for scope in Scope:
            l = session.query(cls).get(scope)
            if not l:
                l = cls(scope=scope, state=State.UNLOCKED)
                session.add(l)
            elif unlock:
                if l.state != State.UNLOCKED:
                    l.state = State.UNLOCKED

    def __repr__(self):
        return f"Locker({self.scope.name}, {self.state.name})"

    def __str__(self):
        return f"Locker({self.scope.name}, {self.state.name})"
