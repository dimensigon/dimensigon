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
    TEST = 0
    ANSIBLE = 1
    PYTHON = 2
    SHELL = 3
    ORCHESTRATION = 4
    REQUEST = 5
    NATIVE = 6



class ActionTemplate(UUIDistributedEntityMixin, db.Model):
    __tablename__ = 'D_action_template'
    order = 10
    name = db.Column(db.String(40), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    action_type = db.Column(typos.Enum(ActionType), nullable=False)
    code = db.Column(db.Text)
    expected_stdout = db.Column(db.Text)
    expected_stderr = db.Column(db.Text)
    expected_rc = db.Column(db.Integer)
    system_kwargs = db.Column(db.JSON)
    pre_process = db.Column(db.Text)
    post_process = db.Column(db.Text)
    schema = db.Column(db.JSON)
    description = db.Column(db.Text)

    def __init__(self, name: str, version: int, action_type: ActionType, code: MultiLine = None,
                 expected_stdout: MultiLine = None, expected_stderr: MultiLine = None,
                 expected_rc: int = None, system_kwargs: typos.Kwargs = None, pre_process: MultiLine = None,
                 post_process: MultiLine = None, schema: typos.Kwargs = None, description: MultiLine = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.version = version
        self.action_type = action_type
        self.code = '\n'.join(code) if is_iterable_not_string(code) else code
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
        self.system_kwargs = self.system_kwargs or {}

    def __str__(self):
        return f"{self.name}.ver{self.version}"

    def to_json(self, split_lines=False, **kwargs):
        data = super().to_json(**kwargs)
        data.update(name=self.name, version=self.version,
                    action_type=self.action_type.name)
        if self.code is not None:
            data.update(code=self.code.split('\n') if split_lines else self.code)
        if self.schema:
            data.update(schema=self.schema)
        if self.system_kwargs:
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
                at = ActionTemplate(name='send software', version=1, action_type=ActionType.NATIVE,
                                    expected_rc=201, last_modified_at=defaults.INITIAL_DATEMARK,
                                    schema={"input": {"software": {"type": "string",
                                                                   "description": "software name or ID to send. If "
                                                                                  "name specified and version not set, "
                                                                                  "biggest version will be taken"},
                                                      "version": {"type": "string",
                                                                  "description": "software version to take"},
                                                      "server": {"type": "string",
                                                                    "description": "destination server id"},
                                                      "dest_path": {"type": "string",
                                                                    "description": "destination path to send software"},
                                                      "chunk_size": {"type": "integer"},
                                                      "max_senders": {"type": "integer"},
                                                      },
                                            "required": ["software", "server"],
                                            "output": ["file"]
                                            },
                                    id='00000000-0000-0000-000a-000000000001',
                                    post_process="import json\nif cp.success:\n  json_data=json.loads(cp.stdout)\n  vc.set('file', "
                                                 "json_data.get('file'))")

                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000002')
            if at is None:
                at = ActionTemplate(name='wait servers', version=1, action_type=ActionType.NATIVE,
                                    description="waits server_names to join to the dimension",
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    schema={"input": {"server_names": {"type": ["array", "string"],
                                                                       "items": {"type": "string"}},
                                                      },
                                            "required": ["server_names"]
                                            },
                                    id='00000000-0000-0000-000a-000000000002')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000003')
            if at is None:
                at = ActionTemplate(name='orchestration', version=1, action_type=ActionType.ORCHESTRATION,
                                    description="launches an orchestration",
                                    schema={"input": {"orchestration": {"type": "string",
                                                                        "description": "orchestration name or ID to "
                                                                                       "execute. If no version "
                                                                                       "specified, the last one will "
                                                                                       "be executed"},
                                                      "version": {"type": "integer"},
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
                                            "required": ["orchestration", "hosts"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000003')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000004')
            if at is None:
                at = ActionTemplate(name='wait route to servers', version=1, action_type=ActionType.NATIVE,
                                    description="waits until we have a valid route to a server",
                                    schema={"input": {"server_names": {"type": ["array", "string"],
                                                                       "items": {"type": "string"}},
                                                      },
                                            "required": ["server_names"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000004')
                session.add(at)
            at = session.query(cls).get('00000000-0000-0000-000a-000000000005')
            if at is None:
                at = ActionTemplate(name='delete servers', version=1, action_type=ActionType.NATIVE,
                                    description="deletes server_names from the dimension",
                                    schema={"input": {"server_names": {"type": ["array", "string"],
                                                                       "items": {"type": "string"}},
                                                      },
                                            "required": ["server_names"]
                                            },
                                    last_modified_at=defaults.INITIAL_DATEMARK,
                                    id='00000000-0000-0000-000a-000000000005')
                session.add(at)
