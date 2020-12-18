import datetime
import typing as t
from collections import ChainMap

from sqlalchemy import orm

from dimensigon import defaults
from dimensigon.domain.entities.base import UUIDistributedEntityMixin
from dimensigon.utils.typos import UUID, ScalarListType, UtcDateTime
from dimensigon.web import db, errors
from .action_template import ActionType
from ...utils import typos
from ...utils.helpers import get_now, is_iterable_not_string, is_valid_uuid

if t.TYPE_CHECKING:
    from .action_template import ActionTemplate
    from .orchestration import Orchestration

step_step = db.Table('D_step_step',
                     db.Column('parent_step_id', UUID, db.ForeignKey('D_step.id'), primary_key=True),
                     db.Column('step_id', UUID, db.ForeignKey('D_step.id'), primary_key=True),
                     )




class Step(UUIDistributedEntityMixin, db.Model):
    __tablename__ = "D_step"
    order = 30
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'), nullable=False)
    action_template_id = db.Column(UUID, db.ForeignKey('D_action_template.id'))
    undo = db.Column(db.Boolean, nullable=False)
    step_stop_on_error = db.Column("stop_on_error", db.Boolean)
    step_stop_undo_on_error = db.Column("stop_undo_on_error", db.Boolean)
    step_undo_on_error = db.Column("undo_on_error", db.Boolean)
    step_expected_stdout = db.Column("expected_stdout", db.Text)
    step_expected_stderr = db.Column("expected_stderr", db.Text)
    step_expected_rc = db.Column("expected_rc", db.Integer)
    step_system_kwargs = db.Column("system_kwargs", db.JSON)
    target = db.Column(ScalarListType(str))
    created_on = db.Column(UtcDateTime(), nullable=False, default=get_now)
    step_action_type = db.Column("action_type", typos.Enum(ActionType))
    step_code = db.Column("code", db.Text)
    step_post_process = db.Column("post_process", db.Text)
    step_pre_process = db.Column("pre_process", db.Text)
    step_name = db.Column("name", db.String(40))
    step_schema = db.Column("schema", db.JSON)
    step_description = db.Column("description", db.Text)

    orchestration = db.relationship("Orchestration", primaryjoin="Step.orchestration_id==Orchestration.id",
                                    back_populates="steps")
    action_template = db.relationship("ActionTemplate", primaryjoin="Step.action_template_id==ActionTemplate.id",
                                      backref="steps")

    parent_steps = db.relationship("Step", secondary="D_step_step",
                                   primaryjoin="D_step.c.id==D_step_step.c.step_id",
                                   secondaryjoin="D_step.c.id==D_step_step.c.parent_step_id",
                                   back_populates="children_steps")

    children_steps = db.relationship("Step", secondary="D_step_step",
                                     primaryjoin="D_step.c.id==D_step_step.c.parent_step_id",
                                     secondaryjoin="D_step.c.id==D_step_step.c.step_id",
                                     back_populates="parent_steps")

    def __init__(self, orchestration: 'Orchestration', undo: bool, action_template: 'ActionTemplate' = None,
                 action_type: ActionType = None, code: str = None, pre_process: str = None, post_process: str = None,
                 stop_on_error: bool = None, stop_undo_on_error: bool = None, undo_on_error: bool = None,
                 expected_stdout: t.Optional[str] = None,
                 expected_stderr: t.Optional[str] = None,
                 expected_rc: t.Optional[int] = None,
                 schema: t.Dict[str, t.Any] = None,
                 system_kwargs: t.Dict[str, t.Any] = None,
                 parent_steps: t.List['Step'] = None, children_steps: t.List['Step'] = None,
                 target: t.Union[str, t.Iterable[str]] = None, name: str = None, description: str = None, rid=None,
                 **kwargs):

        super().__init__(**kwargs)
        assert undo in (False, True)
        if action_template is not None:
            assert action_type is None
        else:
            assert action_type is not None
        self.undo = undo
        self.step_stop_on_error = stop_on_error if stop_on_error is not None else kwargs.pop('step_stop_on_error', None)
        self.step_stop_undo_on_error = stop_undo_on_error if stop_undo_on_error is not None else kwargs.pop(
            'step_stop_undo_on_error', None)
        self.step_undo_on_error = undo_on_error if undo_on_error is not None else kwargs.pop('step_undo_on_error', None)
        self.action_template = action_template
        self.step_action_type = action_type if action_type is not None else kwargs.pop('step_action_type', None)

        expected_stdout = expected_stdout if expected_stdout is not None else kwargs.pop(
            'step_expected_stdout', None)
        self.step_expected_stdout = '\n'.join(expected_stdout) if is_iterable_not_string(
            expected_stdout) else expected_stdout

        expected_stderr = expected_stderr if expected_stderr is not None else kwargs.pop(
            'step_expected_stderr', None)
        self.step_expected_stderr = '\n'.join(expected_stderr) if is_iterable_not_string(
            expected_stderr) else expected_stderr

        self.step_expected_rc = expected_rc if expected_rc is not None else kwargs.pop('step_expected_rc', None)
        self.step_schema = schema if schema is not None else kwargs.pop('step_schema', None) or {}
        self.step_system_kwargs = system_kwargs if system_kwargs is not None else kwargs.pop('step_system_kwargs',
                                                                                             None) or {}
        code = code if code is not None else kwargs.pop('step_code', None)
        self.step_code = '\n'.join(code) if is_iterable_not_string(code) else code

        post_process = post_process if post_process is not None else kwargs.pop('step_post_process', None)
        self.step_post_process = '\n'.join(post_process) if is_iterable_not_string(post_process) else post_process

        pre_process = pre_process if pre_process is not None else kwargs.pop('step_pre_process', None)
        self.step_pre_process = '\n'.join(pre_process) if is_iterable_not_string(pre_process) else pre_process

        self.orchestration = orchestration
        self.parent_steps = parent_steps or []
        self.children_steps = children_steps or []
        if self.undo is False:
            if target is None:
                self.target = ['all']
            else:
                self.target = [target] if isinstance(target, str) else (target if len(target) > 0 else ['all'])
        else:
            if target:
                raise errors.BaseError('target must not be set when creating an UNDO step')
        self.created_on = kwargs.get('created_on') or get_now()
        self.step_name = name if name is not None else kwargs.pop('step_name', None)

        description = description if description is not None else kwargs.pop('step_description', None)
        self.step_description = '\n'.join(description) if is_iterable_not_string(description) else description
        self.rid = rid  # used when creating an Orchestration

    @orm.reconstructor
    def init_on_load(self):
        self.system_kwargs = self.system_kwargs or {}

    @property
    def parents(self):
        return self.parent_steps

    @property
    def children(self):
        return self.children_steps

    @property
    def parent_undo_steps(self):
        return [s for s in self.parent_steps if s.undo == True]

    @property
    def children_undo_steps(self):
        return [s for s in self.children_steps if s.undo == True]

    @property
    def parent_do_steps(self):
        return [s for s in self.parent_steps if s.undo == False]

    @property
    def children_do_steps(self):
        return [s for s in self.children_steps if s.undo == False]

    @property
    def stop_on_error(self):
        return self.step_stop_on_error if self.step_stop_on_error is not None else self.orchestration.stop_on_error

    @stop_on_error.setter
    def stop_on_error(self, value):
        self.step_stop_on_error = value

    @property
    def stop_undo_on_error(self):
        return self.step_stop_undo_on_error if self.step_stop_undo_on_error is not None \
            else self.orchestration.stop_undo_on_error

    @stop_undo_on_error.setter
    def stop_undo_on_error(self, value):
        self.step_stop_undo_on_error = value

    @property
    def undo_on_error(self):
        if self.undo:
            return None
        return self.step_undo_on_error if self.step_undo_on_error is not None else self.orchestration.undo_on_error

    @undo_on_error.setter
    def undo_on_error(self, value):
        self.step_undo_on_error = value

    @property
    def schema(self):
        if self.action_template:
            schema = dict(ChainMap(self.step_schema, self.action_template.schema))
        else:
            schema = dict(self.step_schema)

        if self.action_type == ActionType.ORCHESTRATION:
            from .orchestration import Orchestration
            mapping = schema.get('mapping', {})
            o = Orchestration.get(mapping.get('orchestration', None), mapping.get('version', None))
            if isinstance(o, Orchestration):
                orch_schema = o.schema
                i = schema.get('input', {})
                i.update(orch_schema.get('input', {}))
                schema.update({'input': i})
                m = schema.get('mapping', {})
                m.update(orch_schema.get('mapping', {}))
                schema.update({'mapping': m})
                r = schema.get('required', [])
                [r.append(k) for k in orch_schema.get('required', []) if k not in r]
                schema.update({'required': r})
                o = schema.get('output', [])
                [o.append(k) for k in orch_schema.get('output', []) if k not in o]
                schema.update({'output': o})
        return schema

    @schema.setter
    def schema(self, value):
        self.step_schema = value

    @property
    def system_kwargs(self):
        if self.action_template:
            return dict(ChainMap(self.step_system_kwargs, self.action_template.system_kwargs))
        else:
            return dict(self.step_system_kwargs)

    @system_kwargs.setter
    def system_kwargs(self, value):
        self.step_system_kwargs = value

    @property
    def code(self):
        if self.step_code is None and self.action_template:
            return self.action_template.code
        else:
            return self.step_code

    @code.setter
    def code(self, value):
        self.step_code = value

    @property
    def action_type(self):
        if self.step_action_type is None and self.action_template:
            return self.action_template.action_type
        else:
            return self.step_action_type

    @action_type.setter
    def action_type(self, value):
        self.step_action_type = value

    @property
    def post_process(self):
        if self.step_post_process is None and self.action_template:
            return self.action_template.post_process
        else:
            return self.step_post_process

    @post_process.setter
    def post_process(self, value):
        self.step_post_process = value

    @property
    def pre_process(self):
        if self.step_pre_process is None and self.action_template:
            return self.action_template.pre_process
        else:
            return self.step_pre_process

    @pre_process.setter
    def pre_process(self, value):
        self.step_pre_process = value

    @property
    def expected_stdout(self):
        if self.step_expected_stdout is None and self.action_template:
            return self.action_template.expected_stdout
        else:
            return self.step_expected_stdout

    @expected_stdout.setter
    def expected_stdout(self, value):
        self.step_expected_stdout = value

    @property
    def expected_stderr(self):
        if self.step_expected_stderr is None and self.action_template:
            return self.action_template.expected_stderr
        else:
            return self.step_expected_stderr

    @expected_stderr.setter
    def expected_stderr(self, value):
        if value == self.action_template.expected_stderr:
            self.step_expected_stderr = None
        else:
            self.step_expected_stderr = value

    @property
    def expected_rc(self):
        if self.step_expected_rc is None and self.action_template:
            return self.action_template.expected_rc
        else:
            return self.step_expected_rc

    @expected_rc.setter
    def expected_rc(self, value):
        if self.action_template and value == self.action_template.expected_rc:
            self.step_expected_rc = None
        else:
            self.step_expected_rc = value

    @property
    def name(self):
        if self.step_name is None and self.action_template:
            return str(self.action_template)
        else:
            return self.step_name

    @name.setter
    def name(self, value):
        self.step_name = value

    @property
    def description(self):
        if self.step_description is None and self.action_template:
            return str(self.action_template)
        else:
            return self.step_description

    @description.setter
    def description(self, value):
        self.step_description = value

    def eq_imp(self, other):
        """
        two steps are equal if they execute the same code with the same parameters even if they are from different
        orchestrations or they are in the same orchestration with different positions

        Parameters
        ----------
        other: Step

        Returns
        -------
        result: bool

        Notes
        -----
        _id and _orchestration are not compared
        """
        if isinstance(other, self.__class__):
            return all([self.undo == other.undo,
                        self.stop_on_error == other.stop_on_error,
                        self.stop_undo_on_error == other.stop_undo_on_error,
                        self.undo_on_error == other.undo_on_error,
                        self.expected_stdout == other.expected_stdout,
                        self.expected_stderr == other.expected_stderr,
                        self.expected_rc == other.expected_rc,
                        self.system_kwargs == other.system_kwargs,
                        self.code == other.code,
                        self.post_process == other.post_process,
                        self.pre_process == other.pre_process,
                        self.action_type == other.action_type,
                        ])
        else:
            raise NotImplemented

    def __str__(self):
        return self.name or self.id

    def __repr__(self):
        return ('Undo ' if self.undo else '') + self.__class__.__name__ + ' ' + str(getattr(self, 'id', ''))

    def _add_parents(self, parents):
        for step in parents:
            if not step in self.parent_steps:
                self.parent_steps.append(step)

    def _remove_parents(self, parents):
        for step in parents:
            if step in self.parent_steps:
                self.parent_steps.remove(step)

    def _add_children(self, children):
        for step in children:
            if not step in self.children_steps:
                self.children_steps.append(step)

    def _remove_children(self, children):
        for step in children:
            if step in self.children_steps:
                self.children_steps.remove(step)

    def to_json(self, add_action=False, split_lines=False, **kwargs):
        data = super().to_json(**kwargs)
        if getattr(self.orchestration, 'id', None):
            data.update(orchestration_id=str(self.orchestration.id))
        if getattr(self.action_template, 'id', None):
            if add_action:
                data.update(action_template=self.action_template.to_json(split_lines=split_lines))
            else:
                data.update(action_template_id=str(self.action_template.id))
        data.update(undo=self.undo)
        data.update(stop_on_error=self.step_stop_on_error) if self.step_stop_on_error is not None else None
        data.update(
            stop_undo_on_error=self.step_stop_undo_on_error) if self.step_stop_undo_on_error is not None else None
        data.update(undo_on_error=self.step_undo_on_error) if self.step_undo_on_error is not None else None
        if self.step_schema:
            data.update(schema=self.step_schema)
        if self.step_expected_stdout is not None:
            data.update(
                expected_stdout=self.step_expected_stdout.split('\n') if split_lines else self.step_expected_stdout)
        if self.step_expected_stderr is not None:
            data.update(
                expected_stderr=self.step_expected_stderr.split('\n') if split_lines else self.step_expected_stderr)
        data.update(expected_rc=self.step_expected_rc) if self.step_expected_rc is not None else None
        data.update(system_kwargs=self.step_system_kwargs) if self.step_system_kwargs is not None else None
        data.update(parent_step_ids=[str(step.id) for step in self.parents])
        if self.step_code is not None:
            data.update(code=self.step_code.split('\n') if split_lines else self.step_code)
        data.update(action_type=self.step_action_type.name) if self.step_action_type is not None else None
        if self.step_post_process is not None:
            data.update(post_process=self.step_post_process.split('\n') if split_lines else self.step_post_process)
        if self.step_pre_process is not None:
            data.update(pre_process=self.step_pre_process.split('\n') if split_lines else self.step_pre_process)
        data.update(created_on=self.created_on.strftime(defaults.DATETIME_FORMAT))
        if self.step_description is not None:
            data.update(description=self.step_description.split('\n') if split_lines else self.step_description)
        if self.step_name is not None:
            data.update(name=self.step_name)

        return data

    @classmethod
    def from_json(cls, kwargs):
        from dimensigon.domain.entities import ActionTemplate, Orchestration
        kwargs = dict(kwargs)
        if 'orchestration_id' in kwargs:
            ident = kwargs.pop('orchestration_id')
            kwargs['orchestration'] = db.session.query(Orchestration).get(ident)
            if kwargs['orchestration'] is None:
                raise errors.EntityNotFound('Orchestration', ident=ident)
        if 'action_template_id' in kwargs:
            ident = kwargs.pop('action_template_id')
            kwargs['action_template'] = db.session.query(ActionTemplate).get(ident)
            if kwargs['action_template'] is None:
                raise errors.EntityNotFound('ActionTemplate', ident=ident)
        if 'action_type' in kwargs:
            kwargs['action_type'] = ActionType[kwargs.pop('action_type')]
        if 'created_on' in kwargs:
            kwargs['created_on'] = datetime.datetime.strptime(kwargs['created_on'], defaults.DATETIME_FORMAT)
        kwargs['parent_steps'] = []
        for parent_step_id in kwargs.pop('parent_step_ids', []):
            ps = Step.query.get(parent_step_id)
            if ps:
                kwargs['parent_steps'].append(ps)
            else:
                raise errors.EntityNotFound('Step', parent_step_id)
        return super().from_json(kwargs)
