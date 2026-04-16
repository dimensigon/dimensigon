"""TrainingCandidate model for the training data feedback loop."""
import uuid

from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web import db


class TrainingCandidate(db.Model):
    __tablename__ = 'L_training_candidate'
    # SQLAlchemy 2.0 compatibility
    __allow_unmapped__ = True

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    orchestration_id = db.Column(UUID, db.ForeignKey('D_orchestration.id'), nullable=False)
    source = db.Column(db.String(40), nullable=False, default='ai_generated')
    success_count = db.Column(db.Integer, nullable=False, default=0)
    quality_score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='tracking')
    reviewer = db.Column(db.String(120), nullable=True)
    reviewed_at = db.Column(UtcDateTime(timezone=True), nullable=True)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    orchestration = db.relationship('Orchestration', backref='training_candidates', lazy='joined')

    def to_json(self):
        return {
            'id': str(self.id) if self.id else None,
            'orchestration_id': str(self.orchestration_id) if self.orchestration_id else None,
            'source': self.source,
            'success_count': self.success_count,
            'quality_score': self.quality_score,
            'status': self.status,
            'reviewer': self.reviewer,
            'reviewed_at': self.reviewed_at.strftime('%Y-%m-%dT%H:%M:%SZ') if self.reviewed_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%dT%H:%M:%SZ') if self.created_at else None,
        }

    def __repr__(self):
        return f'<TrainingCandidate {self.id} orch={self.orchestration_id} status="{self.status}">'
