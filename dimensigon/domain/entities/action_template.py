import copy
from enum import Enum

from sqlalchemy import orm

from dimensigon import defaults
from dimensigon.domain.entities.base import UUIDistributedEntityMixin
from dimensigon.utils import typos
from dimensigon.utils.helpers import is_iterable_not_string
from dimensigon.utils.typos import MultiLine
from dimensigon.web import db


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
    parameters = db.Column(db.JSON)  # deprecated. schema attribute used instead
    expected_stdout = db.Column(db.Text)
    expected_stderr = db.Column(db.Text)
    expected_rc = db.Column(db.Integer)
    system_kwargs = db.Column(db.JSON)
    pre_process = db.Column(db.Text)
    post_process = db.Column(db.Text)
    schema = db.Column(db.JSON)  # added in SCHEMA_VERSION = 6
    description = db.Column(db.Text)  # added in SCHEMA_VERSION = 6

    def __init__(self, name: str, version: int, action_type: ActionType, code: MultiLine = None,
                 parameters: typos.Kwargs = None, expected_stdout: MultiLine = None, expected_stderr: MultiLine = None,
                 expected_rc: int = None, system_kwargs: typos.Kwargs = None, pre_process: MultiLine = None,
                 post_process: MultiLine = None, schema: typos.Kwargs = None, description: MultiLine = None, **kwargs):
        UUIDistributedEntityMixin.__init__(self, **kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = '\n'.join(code) if is_iterable_not_string(code) else code
        self.parameters = parameters or {}
        self.schema = schema or {}
        self.expected_stdout = '\n'.join(expected_stdout) if is_iterable_not_string(
            expected_stdout) else expected_stdout
        self.expected_stderr = '\n'.join(expected_stderr) if is_iterable_not_string(
            expected_stderr) else expected_stderr
        self.expected_rc = expected_rc
        self.system_kwargs = system_kwargs or {}
        self.pre_process = '\n'.join(pre_process) if is_iterable_not_string(pre_process) else pre_process
        self.post_process = '\n'.join(post_process) if is_iterable_not_string(post_process) else post_process
        self.description = '\n'.join(description) if is_iterable_not_string(description) else description

    __table_args__ = (db.UniqueConstraint('name', 'version'),)

    @orm.reconstructor
    def init_on_load(self):
        self.parameters = self.parameters or {}
        self.system_kwargs = self.system_kwargs or {}

    def __str__(self):
        return f"{self.name}.ver{self.version}"

    def to_json(self, split_lines=False):
        data = super().to_json()
        data.update(name=self.name, version=self.version,
                    action_type=self.action_type.name,
                    code=self.code.split('\n') if split_lines else self.code)
        if self.parameters is not None:
            data.update(parameters=self.parameters)
        if self.schema is not None:
            data.update(schema=self.schema)
        if self.parameters is not None:
            data.update(system_kwargs=self.system_kwargs)
        if self.expected_stdout is not None:
            data.update(expected_stdout=self.expected_stdout.split('\n') if split_lines else self.expected_stdout)
        if self.expected_stderr is not None:
            data.update(expected_stderr=self.expected_stderr.split('\n') if split_lines else self.expected_stderr)
        if self.expected_rc is not None:
            data.update(expected_rc=self.expected_rc)
        if self.post_process is not None:
            data.update(post_process=self.post_process.split('\n') if split_lines else self.post_process)
        if self.pre_process is not None:
            data.update(pre_process=self.pre_process.split('\n') if split_lines else self.pre_process)
        return data

    @classmethod
    def from_json(cls, kwargs):
        kwargs = copy.deepcopy(kwargs)
        kwargs['action_type'] = ActionType[kwargs.get('action_type')]
        return super().from_json(kwargs)

    @classmethod
    def set_initial(cls, session=None):
        from dimensigon.domain.entities import bypass_datamark_update

        if session is None:
            session = db.session

        with bypass_datamark_update(session):
            at = session.query(cls).get('00000000-0000-0000-000a-000000000001')
            if at is None:
                at = ActionTemplate(name='send', version=1, action_type=ActionType.REQUEST,
                                    code='{"method": "post",' \
                                         '"view":"api_1_0.send",' \
                                         '"json": {"software_id": "{{input.software_id}}", ' \
                                         '         "dest_server_id": "{{input.server_id}}"' \
                                         '{% if input.dest_path %}, "dest_path":"{{input.dest_path}}"{% endif %}' \
                                         '{% if input.chunk_size %}, "chunk_size":"{{input.chunk_size}}"{% endif %}' \
                                         '{% if input.max_senders %}, "max_senders":"{{input.max_senders}}"{% endif %}' \
                                         ', "background": false, "include_transfer_data": true, "force": true} }',
                                    expected_rc=201, last_modified_at=defaults.INITIAL_DATEMARK,
                                    schema={"input": {"software_id": {"type": "string",
                                                                      "description": "software id to send"},
                                                      "server_id": {"type": "string",
                                                                    "description": "destination server id"},
                                                      "dest_path": {"type": "string",
                                                                    "description": "destination path to send software"},
                                                      "chunk_size": {"type": "integer"},
                                                      "max_senders": {"type": "integer"},
                                                      },
                                            "required": ["software_id", "server_id"],
                                            "output": {"file": {"type": "string",
                                                                "description": "absolute path file name"}}
                                            },
                                    id='00000000-0000-0000-000a-000000000001',
                                    post_process="if cp.success:\n  json_data=json.loads(cp.stdout)\n  vc.set('file', "
                                                 "json_data.get('file'))")

                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000002')
            if at is None:
                at = ActionTemplate(name='wait', version=1, action_type=ActionType.NATIVE,
                                    code="",
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    schema={"input": {"list_server_names": {"type": "array",
                                                                            "items": {"type": "string"}},
                                                      "timeout": {"type": "integer"}
                                                      },
                                            "required": ["list_server_names"]
                                            },
                                    id='00000000-0000-0000-000a-000000000002')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000003')
            if at is None:
                at = ActionTemplate(name='orchestration', version=1, action_type=ActionType.ORCHESTRATION,
                                    code="",
                                    schema={"input": {"orchestration_id": {"type": "string"},
                                                      "hosts": {"type": ["string", "array", "object"],
                                                                "items": {"type": "string"},
                                                                "minItems": 1,
                                                                "patternProperties": {
                                                                    ".*": {"anyOf": [{"type": "string"},
                                                                                     {"type": "array",
                                                                                      "items": {"type": "string"},
                                                                                      "minItems": 1
                                                                                      },
                                                                                     ]
                                                                           },
                                                                },
                                                                },
                                                      },
                                            "required": ["orchestration_id", "hosts"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000003')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000004')
            if at is None:
                at = ActionTemplate(name='dm running', version=1, action_type=ActionType.NATIVE,
                                    code="",
                                    schema={"input": {"list_server_names": {"type": "array",
                                                                            "items": {"type": "string"}},
                                                      "timeout": {"type": "integer"}
                                                      },
                                            "required": ["list_server_names"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000004')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000005')
            if at is None:
                at = ActionTemplate(name='delete servers', version=1, action_type=ActionType.NATIVE,
                                    code="",
                                    schema={"input": {"list_server_names": {"type": "array",
                                                                            "items": {"type": "string"}},
                                                      },
                                            "required": ["list_server_names"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000005')
                session.add(at)
