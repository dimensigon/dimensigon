"""Audit log entity for tracking user actions."""
import uuid

from sqlalchemy import Column, String, JSON, Index

from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class AuditEntry(db.Model):
    __tablename__ = 'L_audit_log'

    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(UtcDateTime, default=get_now, nullable=False)
    user_id = Column(String(36), nullable=True)
    username = Column(String(256), nullable=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(128), nullable=True)
    resource_id = Column(String(256), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)

    __table_args__ = (
        Index('ix_audit_log_timestamp', 'timestamp'),
        Index('ix_audit_log_user_id', 'user_id'),
    )

    def __repr__(self):
        return f'<AuditEntry {self.action} by {self.username} at {self.timestamp}>'
