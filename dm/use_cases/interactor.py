import asyncio
import concurrent
import os
import threading
import time
import typing as t
from asyncio import AbstractEventLoop
from collections import ChainMap
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime

from flask import current_app
from marshmallow import ValidationError
from returns.pipeline import is_successful
from returns.result import Result
from returns.result import safe

import dm.use_cases.deployment as dpl

from dm.domain.exceptions import StateAlreadyInUnlock
from dm.domain.locker import PriorityLocker
import dm.framework.exceptions as fmw_exc
import dm.use_cases.exceptions as ue
from dm.framework.domain import Repository
from dm.framework.utils.collection import is_iterable, is_collection
from dm.repositories.repositories import DataMarkRepo

from dm.use_cases.base import OperationFactory, Scope
from dm.use_cases.exceptions import ServersMustNotBeBlank, ErrorLock
from dm.use_cases.helpers import get_servers_from_scope
from dm.use_cases.mediator import Mediator
from dm.utils.async_operator import AsyncOperator
from dm.utils.decorators import logged

if t.TYPE_CHECKING:
    from dm.domain.catalog_manager import CatalogManager
    from dm.domain.entities import Orchestration, Dimension
    from dm import Server
    from dm import Params
    from dm.domain.entities.log import Log


@logged
class Interactor:
    """
    border between user world and domain application world
    """

    def __init__(self, catalog: 'CatalogManager' = None, server: 'Server' = None):
        self.MAX_LINES = 1000
        self.op_factory = OperationFactory()
        self._lockers = {}
        self._catalog = catalog
        for s in Scope:
            self._lockers.update({s: PriorityLocker(s)})
        self._mediator = Mediator(async_operator=AsyncOperator(), interactor=self, server=server)
        self._log_thread = None
        self._logs: t.List[Log] = []
        self._loop = None
        self._group = None
        self.is_running = threading.Event()  # event tells if send_data_log is running
        self._awake = threading.Event()
        self.max_workers = min(32, os.cpu_count() + 4)

    def set_catalog(self, catalog: 'CatalogManager'):
        if not self._catalog:
            self._catalog = catalog

    def set_server(self, server: 'Server'):
        if not self._mediator.server:
            self._mediator.server = server

    def set_dimension(self, dimension: 'Dimension'):
        self._mediator.set_dimension(dimension)

    @property
    def server(self):
        return self._mediator.server

    @property
    def catalog(self):
        return self._catalog

    @property
    def lockers(self):
        return self._lockers

    @property
    def mediator(self):
        return self._mediator

    def stop_timer(self):
        """Stop the timer if it started"""
        for l in self._lockers.values():
            l.stop_timer()

    def _create_cmd_from_orchestration(self, orchestration: 'Orchestration', params: 'Params') -> dpl.CompositeCommand:
        def convert2cmd(d, mapping):
            nd = {}
            for k, v in d.items():
                nd.update({mapping[k]: [mapping[s] for s in v]})
            return nd

        undo_step_cmd_map = {s: dpl.UndoCommand(implementation=self.op_factory.create_operation(s),
                                                params=ChainMap(params, s.parameters),
                                                id_=s.id)
                             for s in orchestration.steps if s.undo}
        step_cmd_map = {}
        tree_step = {}

        for s in (s for s in orchestration.steps if not s.undo):
            tree_step.update({s: [s for s in orchestration.children[s] if not s.undo]})

            # create Undo CompositeCommand for every command
            cc_tree = convert2cmd(orchestration.subtree([s for s in orchestration.children[s] if s.undo]),
                                  undo_step_cmd_map)

            c = dpl.Command(self.op_factory.create_operation(s), undo_implementation=dpl.CompositeCommand(cc_tree),
                            params=ChainMap(params, s.parameters), id_=s.id)

            step_cmd_map.update({s: c})

        return dpl.CompositeCommand(convert2cmd(tree_step, step_cmd_map))

    # TODO implement safe function with the decorator @safe
    def deploy_orchestration(self, orchestration: 'Orchestration', params: 'Params'):
        """

        Parameters
        ----------
        orchestration
            orchestration to deploy
        params
            parameters to pass to the steps

        Returns
        -------
        t.Tuple[bool, bool, t.Dict[int, dpl.Execution]]:
            tuple with 3 values. (boolean indicating if invoke process ended up successfully,
            boolean indicating if undo process ended up successfully,
            dict with all the executions). If undo process not executed, boolean set to None
        """
        cc = self._create_cmd_from_orchestration(orchestration, params)

        res_do, res_undo = None, None
        res_do = cc.invoke()
        if not res_do:
            res_undo = cc.undo()

        return res_do, res_undo, cc.execution

    @safe
    def lock(self, scope: Scope, servers: t.List['Server'] = None):
        """
        locks the Locker if allowed
        Parameters
        ----------
        scope
            scope that lock will affect.
        servers
            if scope set to Scope.ORCHESTRATION,
        Returns
        -------
        Result
        """

        if scope.ORCHESTRATION == scope and servers is None:
            raise ServersMustNotBeBlank()

        servers = servers or get_servers_from_scope(scope)
        self._lockers[scope].preventing_lock(lockers=self._lockers, applicant=servers)
        try:
            self._mediator.lock_unlock('L', scope, servers=servers)
            self._lockers[scope].lock(applicant=servers)
        except ErrorLock as e:
            error_servers = [es.server for es in e]
            locked_servers = list(set(servers) - set(error_servers))
            self._mediator.lock_unlock('U', scope, servers=locked_servers)
            try:
                self._lockers[scope].unlock(applicant=servers)
            except StateAlreadyInUnlock:
                pass
            raise

    @safe
    def unlock(self, scope: Scope):
        """
        unlocks the Locker if allowed
        Parameters
        ----------
        scope

        Returns
        -------

        """
        servers = self._lockers[scope].applicant
        self._lockers[scope].unlock(applicant=servers)
        self._mediator.lock_unlock('U', scope, servers)

    @safe
    def upgrade_catalog(self, server):
        from dm.web import repo_manager as repo_manager, catalog_manager

        result = self.lock(Scope.UPGRADE, [server])

        if is_successful(result):
            delta_catalog = self._mediator.remote_get_delta_catalog(data_mark=self._catalog.max_data_mark,
                                                                    server=server)
            repos: t.List[Repository] = [repo for repo in repo_manager if
                                         isinstance(repo, DataMarkRepo)]
            inside = set(r.__class__.__name__ for r in repos)

            outside = set(delta_catalog.keys())

            if len(inside ^ outside) > 0:
                raise ue.CatalogMismatch(inside ^ outside)

            for r in repos:
                repo_name = r.__class__.__name__
                if repo_name in delta_catalog:
                    for dto in delta_catalog[r.__class__.__name__]:
                        r.dao.upsert(dto)
                        catalog_manager.update_data_mark(r.entity.__name__, dto.get('data_mark'))

            result = self.unlock(Scope.UPGRADE)
            return result
        else:
            return result

    def _main_send_data_logs(self, delay, app=None):

        def send_data_log(log: 'Log'):
            data = ''.join(log.readlines())

            if data:
                try:
                    self._mediator.send_data_log(filename=log.dest_name or os.path.basename(log.file),
                                                 server=log.server,
                                                 data_log=data, dest_folder=log.dest_folder)
                except ue.CommunicationError as e:
                    server, response, code = e.args
                    if isinstance(response, dict):
                        response = response.get('error', response)
                    self.logger.error(
                        f"SendDataLog: Error while trying to communicate with server {str(server)}: {response}")
                else:
                    log.update_offset_file()

        from dm.web import repo_manager

        self.is_running.set()
        self._awake.clear()
        while self.is_running.is_set():
            start = time.time()
            with app.app_context():
                self._logs = repo_manager.LogRepo.all()

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers,
                                                       thread_name_prefix="send_log") as executor:
                future_to_log = {executor.submit(send_data_log, log): log for log in self._logs}

                for future in concurrent.futures.as_completed(future_to_log):
                    log = future_to_log[future]
                    try:
                        data = future.result()
                    except Exception:
                        self.logger.error(f"Error while trying to send data log {log}", exc_info=True)

            for _ in range(len(self._logs)):
                log = self._logs.pop()
                del log
            elapsed = time.time() - start
            self._awake.wait(None if delay is None else max(0 - elapsed, 0))

    def send_data_logs(self, blocking=True, delay=20):
        if not self.is_running.is_set() and self._log_thread is None and len(self._logs) == 0:
            if blocking:
                self._main_send_data_logs(delay, app=current_app._get_current_object())
            else:
                self._log_thread = threading.Thread(target=self._main_send_data_logs, args=(delay,),
                                                    kwargs=dict(app=current_app._get_current_object()),
                                                    name="SendDataLog")
                self._log_thread.start()
                self._log_thread.is_alive()

    def stop_send_data_logs(self):
        # abort thread
        self.is_running.clear()

        # awake thread if sleeping and wait until is stopped
        self._awake.set()

        if self._log_thread is not None:
            self._log_thread.join(120)
            if self._log_thread.is_alive():
                self.logger.error("Unable to stop Send Data Log Thread")
            else:
                self._log_thread = None

        # close all filehandlers pointing to the log files
        for _ in range(len(self._logs)):
            log = self._logs.pop()
            del log
