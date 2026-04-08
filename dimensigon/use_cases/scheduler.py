"""Scheduler service for cron-based orchestration execution."""
import logging
import threading
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
                # TODO: Actually launch orchestration execution here
                # e.g. OrchExecution(orchestration_id=schedule.orchestration_id, ...)

            if due:
                db.session.commit()
