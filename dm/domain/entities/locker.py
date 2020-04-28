from enum import Enum

from dm.utils.typos import Pickle
from dm.web import db


class Scope(Enum):
    ORCHESTRATION = 1  # execute an orchestration
    CATALOG = 2  # lock catalog for updating information
    UPGRADE = 3  # upgrading Catalog from another server

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
    applicant = db.Column(Pickle)

    def __repr__(self):
        return f"Locker({self.scope.name}, {self.state.name})"

    def __str__(self):
        return f"Locker({self.scope.name}, {self.state.name})"
