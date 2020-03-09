from enum import Enum

from dm.utils.typos import Pickle
from dm.web import db


class Scope(Enum):
    UPGRADE = 10
    ORCHESTRATION = 30
    CATALOG = 40

    def __lt__(self, other):
        return self.value < other.value


class State(Enum):
    UNLOCKED = 1
    PREVENTING = 2
    LOCKED = 3


class Locker(db.Model):
    __tablename__ = 'L_locker'

    scope = db.Column(db.Enum(Scope), primary_key=True)
    state = db.Column(db.Enum(State), nullable=False)
    priority = db.Column(db.Integer, nullable=False)
    applicant = db.Column(Pickle)

    @staticmethod
    def fill_data():
        for scope in Scope:
            l = Locker.query.get(scope)
            if not l:
                l = Locker(scope=scope, state=State.UNLOCKED, priority=scope.value)
                db.session.add(l)

    def __repr__(self):
        return f"Locker({self.scope.name}, {self.state.name})"

    def __str__(self):
        return f"Locker({self.scope.name}, {self.state.name})"
