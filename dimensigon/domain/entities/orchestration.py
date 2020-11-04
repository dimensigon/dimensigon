import itertools
import typing as t

import jinja2
from sqlalchemy import orm

from dimensigon.domain.entities.base import UUIDistributedEntityMixin
from dimensigon.domain.entities import ActionType
from dimensigon.utils.dag import DAG
from dimensigon.web import db, errors
from .step import Step
from ...utils.helpers import get_now, is_iterable_not_string
from ...utils.typos import UtcDateTime

if t.TYPE_CHECKING:
    from dimensigon.domain.entities import ActionTemplate

Tdependencies = t.Union[t.Dict[Step, t.Iterable[Step]], t.Iterable[t.Tuple[Step, Step]]]


class Orchestration(db.Model, UUIDistributedEntityMixin):
    __tablename__ = 'D_orchestration'
    order = 20

    name = db.Column(db.String(80), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    stop_on_error = db.Column(db.Boolean)
    stop_undo_on_error = db.Column(db.Boolean)
    undo_on_error = db.Column(db.Boolean)
    parameters = db.Column("parameters", db.JSON)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    steps = db.relationship("Step", primaryjoin="Step.orchestration_id==Orchestration.id",
                            back_populates="orchestration")

    __table_args__ = (db.UniqueConstraint('name', 'version', name='D_orchestration_uq01'),)

    def __init__(self, name: str, version: int, description: t.Optional[str] = None, steps: t.List[Step] = None,
                 stop_on_error: bool = True, stop_undo_on_error: bool = True, undo_on_error: bool = True,
                 parameters=None,
                 dependencies: Tdependencies = None, created_at=None, **kwargs):

        UUIDistributedEntityMixin.__init__(self, **kwargs)

        self.name = name
        self.version = version
        self.description = '\n'.join(description) if is_iterable_not_string(description) else description
        self.steps = steps or []
        assert isinstance(stop_on_error, bool)
        self.stop_on_error = stop_on_error
        assert isinstance(stop_undo_on_error, bool)
        self.stop_undo_on_error = stop_undo_on_error
        assert isinstance(undo_on_error, bool)
        self.undo_on_error = undo_on_error
        self.parameters = parameters or {}
        self.created_at = created_at or get_now()

        if dependencies:
            self.set_dependencies(dependencies)
        else:
            self._graph = DAG()

    @orm.reconstructor
    def init_on_load(self):
        self.parameters = self.parameters or {}
        self._graph = DAG()
        for step in self.steps:
            if step.parents:
                for p in step.parents:
                    self._graph.add_edge(p, step)
            else:
                self._graph.add_node(step)

    def set_dependencies(self, dependencies: Tdependencies):
        edges = []
        find = lambda id_: next((step for step in self.steps if step.id == id_))
        if isinstance(dependencies, t.Dict):
            for k, v in dependencies.items():
                try:
                    step_from = find(k)
                except StopIteration:
                    raise ValueError(f'id step {k} not found in steps list')
                for child_id in v:
                    try:
                        step_to = find(child_id)
                    except StopIteration:
                        raise ValueError(f'id step {child_id} not found in steps list')
                    edges.append((step_from, step_to))
        elif isinstance(dependencies, t.Iterable):
            edges = dependencies
        else:
            raise ValueError(f'dependencies must be a dict like object or an iterable of tuples. '
                             f'See the docs for more information')
        self._graph = DAG(edges)

    @property
    def parents(self) -> t.Dict[Step, t.List[Step]]:
        return self._graph.pred

    @property
    def children(self) -> t.Dict[Step, t.List[Step]]:
        return self._graph.succ

    @property
    def dependencies(self) -> t.Dict[Step, t.List[Step]]:
        return self.children

    @property
    def root(self) -> t.List[Step]:
        return self._graph.root

    @property
    def target(self) -> t.Set[str]:
        target = set()
        for step in self.steps:
            if step.undo is False:
                target.update(step.target)
        return target

    @property
    def user_parameters(self) -> t.Set['str']:
        params = set()
        for s in self.steps:
            params = params.union(s.user_parameters)
        return params - set(self.parameters.keys()) - set(itertools.chain(*[list(s.parameters.keys()) for s in self.steps]))

    def _step_exists(self, step: t.Union[t.List[Step], Step]):
        """Checks if all the steps belong to the current orchestration

        Parameters
        ----------
        step: list[Step]|Step
            Step or list of steps to be evaluated

        Returns
        -------
        None

        Raises
        ------
        ValueError: if any step passed as argument is not in the orchestration
        """
        if not isinstance(step, list):
            steps = [step]
        else:
            steps = step

        for step in steps:
            if not (step in self._graph.nodes and step.orchestration is self):
                raise ValueError(f'{step} is NOT from this orchestration')

    def _check_dependencies(self, step, parents=None, children=None):
        """
        Checks if the dependencies that are going to be added accomplish the business rules. These rules are:
            1. a 'do' Step cannot be preceded for an 'undo' Step
            2. cannot be cycles inside the orchestration

        Parameters
        ----------
        step: Step
            step to be evaluated
        parents: list[Step]
            parent steps to be added
        children: list[Step]
            children steps to be added

        Raises
        ------
        ValueError
            if the rule 1 is not passed
        CycleError
            if the rule 2 is not passed
        """
        parents = parents or []
        children = children or []
        if parents:
            if any([p.undo for p in parents]) and not step.undo:
                attr = 'rid' if step.rid is not None else 'id'
                raise errors.ParentUndoError(getattr(step, attr), [getattr(s, attr) for s in parents if s.undo])
        if children:
            if any([not c.undo for c in children]) and step.undo:
                attr = 'rid' if step.rid is not None else 'id'
                raise errors.ChildDoError(getattr(step, attr), [getattr(s, attr) for s in children if s.undo])
        g = self._graph.copy()
        g.add_edges_from([(p, step) for p in parents])
        g.add_edges_from([(step, c) for c in children])
        if g.is_cyclic():
            raise errors.CycleError()

    def add_step(self, *args, parents=None, children=None, **kwargs) -> Step:
        """Allows to add step into the orchestration

        :param args: args passed to Step: undo, action_template.
        :param parents: list of parent steps.
        :param children: list of children steps.
        :param kwargs: keyword arguments passed to the Step
        :return: The step created.
        """
        parents = parents or []
        children = children or []
        s = Step(None, *args, **kwargs)
        self._step_exists(parents + children)
        self._check_dependencies(s, parents, children)
        s.orchestration = self
        self._graph.add_node(s)
        self.add_parents(s, parents)
        self.add_children(s, children)
        return s

    def delete_step(self, step: Step) -> 'Orchestration':
        """
        Allows to remove a Step from the orchestration

        Parameters
        ----------
        step Step: step to remove from the orchestration
        """
        self._step_exists(step)
        i = self.steps.index(step)
        self.steps.pop(i)
        self._graph.remove_node(step)
        return self

    def add_parents(self, step: Step, parents: t.List[Step]) -> 'Orchestration':
        """add_parents adds the parents passed into the step. No remove from previous parents

        Parameters
        ----------
        step: Step
            step to add parents
        parents: list
            list of parent steps to add

        See Also
        --------
        set_parents, delete_parents
        add_children, set_children, delete_children

        Examples
        --------
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.SHELL, code='code to run',
                                parameters={'param1': 'test'}, expected_output='',
                                expected_rc=0, system_kwargs={})
        >>> o = Orchestration('Test Orchestration', 1, DAG(), 'description')
        >>> s1 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s2 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s3 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> o.add_parents(s2, [s1])
        >>> o.parents[s2]
        [Step1]
        >>> o.add_parents(s2, [s3])
        >>> o.parents[s2]
        [Step1, Step3]
        """
        self._step_exists([step] + list(parents))
        self._check_dependencies(step, parents=parents)
        step._add_parents(parents)
        self._graph.add_edges_from([(p, step) for p in parents])
        return self

    def delete_parents(self, step: Step, parents: t.List[Step]) -> 'Orchestration':
        """delete_parents deletes the parents passed from the step.

        Parameters
        ----------
        step: Step
            step to remove parents
        parents: list
            list of parent steps to remove

        See Also
        --------
        add_parents, set_parents
        add_children, set_children, delete_children

        Examples
        --------
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.SHELL, code='code to run',
                                parameters={'param1': 'test'}, expected_output='',
                                expected_rc=0, system_kwargs={})
        >>> o = Orchestration('Test Orchestration', 1, DAG(), 'description')
        >>> s1 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s2 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s3 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> o.add_children(s1, [s2, s3])
        >>> o.children[s1]
        [Step2, Step3]
        >>> o.delete_parents(s3, [s1])
        >>> o.children[s1]
        [Step2]
        """
        self._step_exists([step] + list(parents))
        step._remove_parents(parents)
        self._graph.remove_edges_from([(p, step) for p in parents])
        return self

    def set_parents(self, step: Step, parents: t.List[Step]) -> 'Orchestration':
        """set_parents sets the parents passed on the step, removing the previos ones

        Parameters
        ----------
        step: Step
            step to remove parents
        parents: list
            list of parent steps to set

        See Also
        --------
        add_parents, delete_parents
        add_children, delete_children, set_children,

        Examples
        --------
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.SHELL, code='code to run',
                                parameters={'param1': 'test'}, expected_output='',
                                expected_rc=0, system_kwargs={})
        >>> o = Orchestration('Test Orchestration', 1, DAG(), 'description')
        >>> s1 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s2 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> s3 = o.add_step(undo=False, action_template=at, parents=[], children=[], stop_on_error=False)
        >>> o.add_parents(s1, [s2])
        >>> o.parents[s1]
        [Step2]
        >>> o.set_parents(s1, [s3])
        >>> o.parents[s1]
        [Step3]
        """
        self.delete_parents(step, self._graph.pred[step])
        self.add_parents(step, parents)
        return self

    def add_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self._step_exists([step] + children)
        self._check_dependencies(step, children=children)
        step._add_children(children)
        self._graph.add_edges_from([(step, c) for c in children])
        return self

    def delete_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self._step_exists([step] + children)
        step._remove_children(children)
        self._graph.remove_edges_from([(step, c) for c in children])
        return self

    def set_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self.delete_children(step, self._graph.succ[step])
        self.add_children(step, children)
        return self

    def eq_imp(self, other: 'Orchestration') -> bool:
        """
        compares if two orchestrations implement same steps with same parameters and dependencies

        Parameters
        ----------
        other: Orchestration

        Returns
        -------
        result: bool
        """
        if isinstance(other, self.__class__):
            if len(self.steps) != len(other.steps):
                return False
            res = []
            for s in self.steps:
                res.append(any(map(lambda x: s.eq_imp(x), other.steps)))

            if all(res):

                matched_steps = []
                res2 = []
                v2 = []
                for k1, v1 in self.children.items():
                    k2 = None
                    for s in filter(lambda x: x not in matched_steps, other.steps):
                        if k1.eq_imp(s):
                            k2 = s
                            v2 = other.children[k2]
                            break
                    if not k2:
                        raise RuntimeError('Step not found in other')
                    matched_steps.append(k2)
                    if len(v1) != len(v2):
                        return False

                    for s in v1:
                        res2.append(any(map(lambda x: s.eq_imp(x), v2)))
                return all(res2)
            else:
                return False
        else:
            return False

    def subtree(self, steps: t.Union[t.List[Step], t.Iterable[Step]]) -> t.Dict[Step, t.List[Step]]:
        return self._graph.subtree(steps)

    def to_json(self, add_target=False, add_params=False, add_steps=False, add_action=False, split_lines=False):
        data = super().to_json()
        data.update(name=self.name, version=self.version, stop_on_error=self.stop_on_error,
                    undo_on_error=self.undo_on_error, stop_undo_on_error=self.stop_undo_on_error)
        if add_target:
            data.update(target=list(self.target))
        if add_steps:
            json_steps = []
            for step in self.steps:
                json_step = step.to_json(add_action=add_action, split_lines=split_lines)
                json_step.pop('orchestration_id')
                json_steps.append(json_step)
            data['steps'] = json_steps
        return data

    @classmethod
    def from_json(cls, kwargs):
        return super().from_json(kwargs)

    def __str__(self):
        return f"{self.name}.{self.version}"

    @property
    def schema(self):
        outer_schema = {'input': {}, 'required': [], 'output': []}
        level = 1
        while level <= self._graph.depth:
            for step in self._graph.get_nodes_at_level(level):
                schema = step.schema
                for k, v in step.schema.get('input', {}).items():
                    if k not in outer_schema['input'] and \
                            k not in outer_schema['output'] and \
                            k not in schema.get('mapping', {}):
                        outer_schema['input'].update({k: v})
                for k, v in step.schema.get('mapping', {}).items():
                    if isinstance(v, dict) and len(v) == 1 and 'from' in v:
                        action, source = tuple(v.items())[0]
                        if not (source in outer_schema['input'] or source in outer_schema['output']):
                            raise errors.MappingError(source, step)
                for k in list(schema.get('output', [])):
                    outer_schema['output'].append(k) if k not in outer_schema['output'] else None
                for k in list(schema.get('required', [])):
                    if k not in outer_schema['output'] and k not in schema.get('mapping', {}):
                        outer_schema['required'].append(k) if k not in outer_schema['required'] else None
            level += 1
        return outer_schema
