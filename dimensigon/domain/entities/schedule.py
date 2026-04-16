"""Schedule model for cron-based orchestration scheduling."""
import uuid

from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web import db


class Schedule(db.Model):
    __tablename__ = 'L_schedule'
    # SQLAlchemy 2.0 compatibility
    __allow_unmapped__ = True

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'), nullable=False)
    cron_expr = db.Column(db.String(120), nullable=False)
    timezone = db.Column(db.String(50), default='UTC')
    enabled = db.Column(db.Boolean, default=True)
    last_run = db.Column(UtcDateTime(timezone=True), nullable=True)
    next_run = db.Column(UtcDateTime(timezone=True), nullable=True)
    missed_policy = db.Column(db.String(20), default='skip')  # 'skip' or 'run_once'
    params = db.Column(db.JSON, nullable=True)
    created_by = db.Column(db.String(120), nullable=True)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    orchestration = db.relationship('Orchestration', backref='schedules', lazy='joined')

    def __repr__(self):
        return f'<Schedule {self.id} orch={self.orchestration_id} cron="{self.cron_expr}" enabled={self.enabled}>'
