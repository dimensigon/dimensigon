import copy
from enum import Enum, auto

from jinja2schema import infer

from dm import defaults
from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils.typos import JSON, Kwargs
from dm.web import db


class ActionType(Enum):
    ANSIBLE = auto()
    PYTHON = auto()
    SHELL = auto()
    ORCHESTRATION = auto()
    REQUEST = auto()
    NATIVE = auto()


class ActionTemplate(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_action_template'
    order = 10
    name = db.Column(db.String(40), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.Enum(ActionType), nullable=False)
    code = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSON)
    expected_stdout = db.Column(db.Text)
    expected_stderr = db.Column(db.Text)
    expected_rc = db.Column(db.Integer)
    system_kwargs = db.Column(JSON)
    post_process = db.Column(db.Text)

    def __init__(self, name: str, version: int, action_type: ActionType, code: str = None, parameters: Kwargs = None,
                 expected_stdout: str = None, expected_stderr: str = None, expected_rc: int = None,
                 system_kwargs: Kwargs = None, post_process: str = None,
                 **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = code
        self.parameters = parameters or {}
        self.expected_stdout = expected_stdout
        self.expected_stderr = expected_stderr
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}
        self.post_process = post_process

    __table_args__ = (db.UniqueConstraint('name', 'version'),)

    def to_json(self):
        data = super().to_json()
        data.update(name=self.name, version=self.version,
                    action_type=self.action_type.name,
                    code=self.code, parameters=self.parameters, expected_stdout=self.expected_stdout,
                    expected_stderr=self.expected_stderr,
                    expected_rc=self.expected_rc, system_kwargs=self.system_kwargs, post_process=self.post_process)
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['action_type'] = ActionType[kwargs.get('action_type')]
        return super().from_json(kwargs)

    @property
    def code_parameters(self):
        return infer(self.code).keys()

    @classmethod
    def set_initial(cls):
        at = cls.query.get('00000000-0000-0000-000a-000000000001')
        if at is None:
            at = ActionTemplate('send', version=1, action_type=ActionType.REQUEST,
                                code='{"method": "post",'
                                     '"view_or_url":"api_1_0.send",'
                                     '"json":{"software_id": "{{software_id}}", "dest_server_id": "{{dest_server_id}}"'
                                     '{% if dest_path is defined %}, "dest_path":"{{dest_path}}"{% endif %}'
                                     '{% if chunk_size is defined %}, "chunk_size":"{{chunk_size}}"{% endif %}'
                                     '{% if max_senders is defined %}, "max_senders":"{{max_senders}}"{% endif %}'
                                     ', "background": false}}',
                                parameters={}, expected_rc=204, last_modified_at=defaults.INITIAL_DATEMARK,
                                id='00000000-0000-0000-000a-000000000001')

            db.session.add(at)
        at = cls.query.get('00000000-0000-0000-000a-000000000002')
        if at is None:
            at = ActionTemplate('wait', version=1, action_type=ActionType.NATIVE,
                                code='{{list_server_names}} {{timeout}}',
                                parameters={}, last_modified_at=defaults.INITIAL_DATEMARK,
                                id='00000000-0000-0000-000a-000000000002')
            db.session.add(at)
