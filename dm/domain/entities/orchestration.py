import typing as t
import uuid
from collections import ChainMap

from dm.domain.entities import ActionTemplate
from dm.domain.exceptions import CycleError
from dm.framework.utils.dependency_injection import Inject
from dm.framework.utils.functools import reify
from dm.utils.dag import DAG
from dm.utils.datamark import data_mark
from dm.framework.domain import Entity, Id
from dm.framework.interfaces.entity import Id as IdType


class Step(Entity):
    __id__ = Id(factory=uuid.uuid1)

    @data_mark
    def __init__(self, undo: bool, stop_on_error: bool,
                 action_template: ActionTemplate, step_expected_output: t.Optional[str] = None,
                 step_expected_rc: t.Optional[int] = None, step_parameters: t.Dict[str, t.Any] = None,
                 step_system_kwargs: t.Dict[str, t.Any] = None, **kwargs):

        super().__init__(**kwargs)
        self.undo = undo
        self.stop_on_error = stop_on_error
        self.action_template = action_template
        self.step_expected_output = step_expected_output
        self.step_expected_rc = step_expected_rc
        self.step_parameters = step_parameters
        self.step_system_kwargs = step_system_kwargs
        self.orchestration = kwargs.get('orchestration')

    @classmethod
    def set_sequence(cls, factory: t.Callable[[], IdType]):
        cls.__id__.factory = factory

    @reify
    def parameters(self):
        return ChainMap(self.step_parameters or {}, self.action_template.parameters)

    @reify
    def system_kwargs(self):
        return ChainMap(self.step_system_kwargs or {}, self.action_template.system_kwargs)

    @property
    def code(self):
        return self.action_template.code

    @property
    def type(self):
        return self.action_template.action_type

    @property
    def expected_output(self):
        return self.step_expected_output if self.step_expected_output is not None else self.action_template.expected_output

    @expected_output.setter
    def expected_output(self, value):
        if value == self.action_template.expected_output:
            self.step_expected_output = None
        else:
            self.step_expected_output = value

    @property
    def expected_rc(self):
        return self.step_expected_rc if self.step_expected_rc is not None else self.action_template.expected_rc

    @expected_rc.setter
    def expected_rc(self, value):
        if value == self.action_template.expected_rc:
            self.step_expected_rc = None
        else:
            self.step_expected_rc = value

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
            return all([self.undo == other.undo, self.parameters == other.parameters,
                        self.expected_output == other.expected_output, self.expected_rc == other.expected_rc,
                        self.system_kwargs == other.system_kwargs, self.code == other.code])
        else:
            raise NotImplemented

    def __str__(self):
        return ('Undo ' if self.undo else '') + self.__class__.__name__ + str(getattr(self, 'id', ''))

    def __repr__(self):
        return self.__str__()


class Orchestration(Entity):
    """
    Parameters
    ----------
    name str:
        Orchestration name
    version int:
        Version of the orchestration
    graph:
        graph hierarchy object
    description str:
        description for the orchestration

    """
    __id__ = Id(factory=uuid.uuid1)

    @data_mark
    def __init__(self, name: str, version: int, description: t.Optional[str] = None,
                 steps: t.List[Step] = None, dependencies: t.Dict[IdType, t.List[IdType]] = None, **kwargs):
        super().__init__(**kwargs)
        find = lambda id_: next((step for step in steps if step.id == id_))
        self.name = name
        self.version = version
        edges = []
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
        self._graph = DAG(edges)
        self.description = description

    @property
    def steps(self) -> t.List[Step]:
        return self._graph.nodes

    @property
    def parents(self) -> t.Dict[Step, t.List[Step]]:
        return self._graph.pred

    @property
    def children(self) -> t.Dict[Step, t.List[Step]]:
        return self._graph.succ

    @property
    def dependencies(self) -> t.Dict[IdType, t.List[IdType]]:
        return {k.id: [vv.id for vv in v] for k, v in self.children.items()}

    @property
    def root(self) -> t.List[Step]:
        return self._graph.root

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
                raise ValueError(f"a 'do' step cannot have parent 'undo' steps")
        if children:
            if any([not c.undo for c in children]) and step.undo:
                raise ValueError(f"an 'undo' step cannot have child 'do' steps")
        g = self._graph.copy()
        g.add_edges_from([(p, step) for p in parents])
        g.add_edges_from([(step, c) for c in children])
        if g.is_cyclic():
            raise CycleError('Cycle detected while trying to add dependency')

    def add_step(self, undo, action_template, parents=None, children=None, stop_on_error=False, **kwargs) -> Step:
        """
        Allows to add step into the orchestration

        Parameters
        ----------
        undo: bool
            defines if the step is an undo step
        action_template: ActionTemplate:
            action tempalte to copy
        parents: list:
            list of parent steps
        children: list:
            list of child steps
        stop_on_error: bool
            stops on error and does not try to execute the undo
        **kwargs: dict
            parameters passed to the Step initializer

        Returns
        -------
        step: Step
            Step created
        """
        parents = parents or []
        children = children or []
        s = Step(orchestration=self, num=len(self.steps) + 1, undo=undo, action_template=action_template,
                 stop_on_error=stop_on_error, **kwargs)
        self._step_exists(parents + children)
        self._check_dependencies(s, parents, children)
        self._graph.add_node(s)
        self._graph.add_edges_from([(p, s) for p in parents])
        self._graph.add_edges_from([(s, c) for c in children])
        return s

    def delete_step(self, step: Step) -> 'Orchestration':
        """
        Allows to remove a Step from the orchestration

        Parameters
        ----------
        step Step: step to remove from the orchestration
        """
        self._step_exists(step)
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
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.NATIVE, code='code to run',
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
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.NATIVE, code='code to run',
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
        >>> at = ActionTemplate(name='action', version=1, action_type=ActionType.NATIVE, code='code to run',
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
        self._step_exists([step] + parents)
        self.delete_parents(step, self._graph.pred[step])
        self.add_parents(step, parents)
        return self

    def add_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self._step_exists([step] + children)
        self._check_dependencies(step, children=children)
        self._graph.add_edges_from([(step, c) for c in children])
        return self

    def set_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self._step_exists([step] + children)
        self._graph.remove_edges_from([(step, c) for c in self._graph.succ[step]])
        self.add_children(step, children)
        return self

    def delete_children(self, step: Step, children: t.List[Step]) -> 'Orchestration':
        self._step_exists([step] + children)
        self._graph.remove_edges_from([(step, c) for c in children])
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

    def __str__(self):
        return f'{getattr(self, "name", None)}.{getattr(self, "version", None)}'
