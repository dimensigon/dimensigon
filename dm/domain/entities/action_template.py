import copy
from enum import Enum

from dm import defaults
from dm.domain.entities.base import UUIDistributedEntityMixin
from dm.utils import typos
from dm.utils.typos import JSON, Kwargs
from dm.web import db


class ActionType(Enum):
    ANSIBLE = 1
    PYTHON = 2
    SHELL = 3
    ORCHESTRATION = 4
    REQUEST = 5
    NATIVE = 6


class ActionTemplate(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_action_template'
    order = 10
    name = db.Column(db.String(40), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    action_type = db.Column(typos.Enum(ActionType), nullable=False)
    code = db.Column(db.Text, nullable=False)
    parameters = db.Column(JSON)
    expected_stdout = db.Column(db.Text)
    expected_stderr = db.Column(db.Text)
    expected_rc = db.Column(db.Integer)
    system_kwargs = db.Column(JSON)
    pre_process = db.Column(db.Text)
    post_process = db.Column(db.Text)

    def __init__(self, name: str, version: int, action_type: ActionType, code: str = None, parameters: Kwargs = None,
                 expected_stdout: str = None, expected_stderr: str = None, expected_rc: int = None,
                 system_kwargs: Kwargs = None, pre_process: str = None, post_process: str = None,
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
        self.pre_process = pre_process
        self.post_process = post_process

    __table_args__ = (db.UniqueConstraint('name', 'version'),)

    def to_json(self):
        data = super().to_json()
        data.update(name=self.name, version=self.version,
                    action_type=self.action_type.name,
                    code=self.code)
        if self.parameters:
            data.update(parameters=self.parameters)
        if self.system_kwargs:
            data.update(system_kwargs=self.system_kwargs)
        if self.expected_stdout is not None:
            data.update(expected_stdout=self.expected_stdout)
        if self.expected_stderr is not None:
            data.update(expected_stderr=self.expected_stderr)
        if self.expected_rc is not None:
            data.update(expected_rc=self.expected_rc)
        if self.pre_process is not None:
            data.update(pre_process=self.pre_process)
        if self.post_process is not None:
            data.update(post_process=self.post_process)
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['action_type'] = ActionType[kwargs.get('action_type')]
        return super().from_json(kwargs)

    @classmethod
    def set_initial(cls):
        from dm.domain.entities import bypass_datamark_update
        with bypass_datamark_update():
            at = cls.query.get('00000000-0000-0000-000a-000000000001')
            if at is None:
                at = ActionTemplate(name='send', version=1, action_type=ActionType.REQUEST,
                                    code='{"method": "post",'\
                                         '"view_or_url":"api_1_0.send",'\
                                         '"json": {"software_id": "{{software_id}}", "dest_server_id": "{{server_id}}"'\
                                         '{% if dest_path is defined %}, "dest_path":"{{dest_path}}"{% endif %}'\
                                         '{% if chunk_size is defined %}, "chunk_size":"{{chunk_size}}"{% endif %}'\
                                         '{% if max_senders is defined %}, "max_senders":"{{max_senders}}"{% endif %}'\
                                         ', "background": false, "include_transfer_data": true, "force": true} }',
                                    expected_rc=201, last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000001',
                                    post_process="json_data=json.loads(cp.stdout)\nvc.set('file', json_data.get('file'))")

                db.session.add(at)
            at = cls.query.get('00000000-0000-0000-000a-000000000002')
            if at is None:
                at = ActionTemplate(name='wait', version=1, action_type=ActionType.NATIVE,
                                    code='{{list_server_names}} {{timeout}}',
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000002')
                db.session.add(at)
            at = cls.query.get('00000000-0000-0000-000a-000000000003')
            if at is None:
                at = ActionTemplate(name='orchestration', version=1, action_type=ActionType.ORCHESTRATION,
                                    code='{{orchestration_id}} {{hosts}}',
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000003')
                db.session.add(at)
