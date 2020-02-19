import uuid
from enum import Enum, auto

import sqlalchemy as sa

from dm.domain.entities.base import DistributedEntityMixin, EntityReprMixin
from dm.model import Base
from dm.utils.typos import JSON, UUID, Params


class ActionType(Enum):
    ANSIBLE = auto()
    PYTHON = auto()
    NATIVE = auto()
    ORCHESTRATION = auto()
    TEST = auto()


class ActionTemplate(EntityReprMixin, DistributedEntityMixin, Base):
    __tablename__ = 'D_action_template'

    id = sa.Column(UUID, primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(40), nullable=False)
    version = sa.Column(sa.Integer, nullable=False)
    action_type = sa.Column(sa.Enum(ActionType), nullable=False)
    code = sa.Column(sa.Text, nullable=False)
    parameters = sa.Column(JSON)
    expected_output = sa.Column(sa.Text)
    expected_rc = sa.Column(sa.Integer)
    system_kwargs = sa.Column(JSON)

    def __init__(self, name: str, version: int, action_type: ActionType, code: str, parameters: Params = None,
                 expected_output: str = None, expected_rc: int = None, system_kwargs: Params = None,
                 id: uuid.UUID = None,
                 **kwargs):
        DistributedEntityMixin.__init__(self, **kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = code
        self.parameters = parameters or {}
        self.expected_output = expected_output
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}
        self.id = id

    # systems = sa.relationship("System", secondary='D_action_system', back_populates="actions")

    __table_args__ = (sa.UniqueConstraint('name', 'version', name='D_action_template_uq01'),)
