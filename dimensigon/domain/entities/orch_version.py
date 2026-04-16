"""OrchestrationVersion model for orchestration versioning and rollback."""
import uuid

from sqlalchemy import Column, Integer, String, ForeignKey, JSON

from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class OrchestrationVersion(db.Model):
    __tablename__ = 'L_orchestration_version'
    __allow_unmapped__ = True

    id = Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    orchestration_id = Column(UUID, ForeignKey('D_orchestration.id'), nullable=False)
    version_number = Column(Integer, nullable=False)
    json_snapshot = Column(JSON, nullable=False)
    author = Column(String(120), nullable=True)
    message = Column(String(500), nullable=True)
    created_at = Column(UtcDateTime(timezone=True), default=get_now)

    orchestration = db.relationship('Orchestration', backref='versions')

    def __repr__(self):
        return f'<OrchestrationVersion orch={self.orchestration_id} v{self.version_number}>'
