import typing as t

from dm.domain.entities import Orchestration, Server, Execution
from dm.use_cases.deployment import create_cmd_from_orchestration2
from dm.utils.typos import Kwargs
from dm.web import db, executor


def deploy_orchestration(orchestration: Orchestration, params: Kwargs, hosts: t.Dict[str, t.List[Server]],
                         max_parallel_tasks=None, auth=None):
    """
    Parameters
    ----------
    orchestration
        orchestration to deploy
    params
        parameters to pass to the steps

    Returns
    -------
    t.Tuple[bool, bool, t.Dict[int, dpl.CompletedProcess]]:
        tuple with 3 values. (boolean indicating if invoke process ended up successfully,
        boolean indicating if undo process ended up successfully,
        dict with all the executions). If undo process not executed, boolean set to None
    """
    cc = create_cmd_from_orchestration2(orchestration, params, hosts=hosts, executor=executor, auth=auth)

    res_do, res_undo = None, None
    res_do = cc.invoke()
    if not res_do and orchestration.undo_on_error:
        res_undo = cc.undo()
    me = Server.get_current()
    for k, cp in cc.result.items():
        e = Execution()
        e.load_completed_result(cp)
        e.step_id = k[1]
        e.execution_server_id = k[0]
        e.source_server_id = me.id
        db.session.add(e)
    db.session.commit()

