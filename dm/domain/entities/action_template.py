import copy
from enum import Enum, auto

from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils.typos import JSON, Params
from dm.web import db


class ActionType(Enum):
    ANSIBLE = auto()
    PYTHON = auto()
    NATIVE = auto()
    ORCHESTRATION = auto()
    TEST = auto()


class ActionTemplate(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_action_template'
    order = 10
    name = db.Column(db.String(40), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.Enum(ActionType), nullable=False)
    code = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSON)
    expected_output = db.Column(db.Text)
    expected_rc = db.Column(db.Integer)
    system_kwargs = db.Column(JSON)

    def __init__(self, name: str, version: int, action_type: ActionType, code: str, parameters: Params = None,
                 expected_output: str = None, expected_rc: int = None, system_kwargs: Params = None,
                 **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = code
        self.parameters = parameters or {}
        self.expected_output = expected_output
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}

    # systems = db.relationship("System", secondary='D_action_system', back_populates="actions")

    __table_args__ = (db.UniqueConstraint('name', 'version'),)

    def to_json(self):
        data = super().to_json()
        data.update(name=self.name, version=self.version,
                    action_type=self.action_type.name,
                    code=self.code, parameters=self.parameters, expected_output=self.expected_output,
                    expected_rc=self.expected_rc, system_kwargs=self.system_kwargs)
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['action_type'] = ActionType[kwargs.get('action_type')]
        return super().from_json(kwargs)
