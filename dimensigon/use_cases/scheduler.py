"""Scheduler service for cron-based orchestration execution."""
import logging
import threading
import uuid
import datetime as dt

from croniter import croniter

_LOGGER = logging.getLogger(__name__)


def compute_next_run(cron_expr, timezone='UTC', after=None):
    """Compute the next run time for a cron expression.

    Args:
        cron_expr: A cron expression string (e.g. '*/5 * * * *').
        timezone: Timezone name (default 'UTC'). Currently only UTC is used
                  for the base datetime; the value is accepted for future use.
        after: A datetime to start from. If None, uses utcnow.

    Returns:
        A timezone-aware datetime (UTC) for the next occurrence.
    """
    if after is None:
        after = dt.datetime.now(dt.timezone.utc)
    # Ensure after is timezone-aware
    if after.tzinfo is None:
        after = after.replace(tzinfo=dt.timezone.utc)
    cron = croniter(cron_expr, after)
    next_dt = cron.get_next(dt.datetime)
    if next_dt.tzinfo is None:
        next_dt = next_dt.replace(tzinfo=dt.timezone.utc)
    return next_dt


class SchedulerService:
    """Background service that polls Schedule records and triggers executions."""

    def __init__(self, app=None, interval=30):
        self._app = app
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the scheduler daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='SchedulerService')
        self._thread.start()
        _LOGGER.info('SchedulerService started (interval=%ds)', self._interval)

    def stop(self):
        """Signal the scheduler to stop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 5)
        _LOGGER.info('SchedulerService stopped')

    def _loop(self):
        """Main loop: every interval seconds, find and execute due schedules."""
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                _LOGGER.exception('SchedulerService tick error')
            self._stop_event.wait(timeout=self._interval)

    def _tick(self):
        """Single tick: query due schedules and trigger them."""
        if self._app is None:
            return

        from dimensigon.domain.entities.schedule import Schedule
        from dimensigon.web import db
        from sqlalchemy import select

        now = dt.datetime.now(dt.timezone.utc)

        with self._app.app_context():
            due = db.session.execute(
                select(Schedule).where(
                    Schedule.enabled == True,  # noqa: E712
                    Schedule.next_run <= now,
                )
            ).scalars().all()

            for schedule in due:
                _LOGGER.info(
                    'Triggering schedule %s (orchestration=%s, cron=%s)',
                    schedule.id, schedule.orchestration_id, schedule.cron_expr,
                )
                schedule.last_run = now
                schedule.next_run = compute_next_run(
                    schedule.cron_expr, schedule.timezone, after=now,
                )
                try:
                    execution_id = self._launch(schedule)
                    _LOGGER.info(
                        'Schedule %s launched orchestration %s as execution %s',
                        schedule.id, schedule.orchestration_id, execution_id,
                    )
                except Exception:
                    # An individual launch failure must not stop the loop or
                    # prevent next_run from advancing for the other schedules.
                    _LOGGER.exception(
                        'Schedule %s: failed to launch orchestration %s',
                        schedule.id, schedule.orchestration_id,
                    )

            if due:
                db.session.commit()

    def _launch(self, schedule):
        """Launch the orchestration referenced by ``schedule``.

        Mirrors the API launch path (``api_1_0.urls.use_cases.launch_orchestration``):
        resolves the executor user, builds the host mapping and variable
        context, then submits :func:`deploy_orchestration` to the shared
        executor so the scheduler loop is not blocked by the run.

        Returns:
            The new OrchExecution id.
        """
        from dimensigon.domain.entities import Orchestration, OrchExecution, Server, User, Vault
        from dimensigon.use_cases.deployment import deploy_orchestration
        from dimensigon.utils.var_context import Context
        from dimensigon.web import db, executor
        from dimensigon.web.helpers import normalize_hosts

        orchestration = db.session.get(Orchestration, schedule.orchestration_id)
        if orchestration is None:
            raise ValueError(f'orchestration {schedule.orchestration_id} not found')
        if not orchestration.steps:
            raise ValueError(f'orchestration {orchestration.id} has no steps to execute')

        # Resolve the executor: prefer the user that created the schedule, fall
        # back to the built-in deployer ('ops') and finally 'root'. Unattended
        # runs still need a concrete User for the OrchExecution row.
        executor_user = None
        if schedule.created_by:
            executor_user = User.get_by_name(schedule.created_by)
        if executor_user is None:
            executor_user = User.get_by_name('ops') or User.get_by_name('root')
        if executor_user is None:
            raise ValueError('no executor user available to run scheduled orchestration')

        # Schedules carry no operator-supplied host map, so default every target
        # granule to the local server, then normalize names/granules to ids.
        current_server = Server.get_current()
        targets = orchestration.target or {'all'}
        hosts = {target: [current_server.id] for target in targets}
        not_found = normalize_hosts(hosts)
        if not_found:
            raise ValueError(f'unresolved hosts for scheduled orchestration: {not_found}')

        execution_id = str(uuid.uuid4())
        params = schedule.params or {}
        var_context = Context(
            params,
            dict(execution_id=None, root_orch_execution_id=execution_id,
                 orch_execution_id=execution_id, executor_id=executor_user.id),
            vault=Vault.get_variables_from(executor_user.id, scope='global'),
        )

        # Pre-create the OrchExecution row inside this app_context/session so the
        # execution is observable immediately and so deploy_orchestration runs in
        # the background executor without needing g.server / a request context.
        exe = OrchExecution(id=execution_id, orchestration_id=orchestration.id, target=hosts,
                            params=dict(var_context), executor_id=executor_user.id,
                            server_id=current_server.id)
        db.session.add(exe)
        db.session.commit()

        # The executor wraps the callable in a copy of the current app context
        # (we are inside self._app.app_context() during the tick), exactly as the
        # API launch path does. Pass ids so the run rebinds entities in its own
        # session; the OrchExecution row created above is rebound via execution=.
        executor.submit(deploy_orchestration, orchestration=orchestration.id,
                        var_context=var_context, hosts=hosts,
                        execution=execution_id, executor=executor_user.id)
        return execution_id
