"""Orchestration Template model for the template marketplace."""
import uuid

from dimensigon.utils.helpers import get_now
from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.web import db


TEMPLATE_CATEGORIES = (
    'deployment', 'monitoring', 'maintenance', 'security', 'networking', 'custom'
)


class OrchTemplate(db.Model):
    __tablename__ = 'L_orch_template'
    # SQLAlchemy 2.0 compatibility
    __allow_unmapped__ = True

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(40), nullable=False, default='custom')
    tags = db.Column(db.JSON, nullable=True, default=list)
    json_content = db.Column(db.JSON, nullable=True)
    rating_sum = db.Column(db.Integer, default=0, nullable=False)
    rating_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(UtcDateTime(timezone=True), default=get_now)

    @property
    def rating(self):
        if self.rating_count and self.rating_count > 0:
            return self.rating_sum / self.rating_count
        return 0

    def to_json(self, include_content=False):
        data = {
            'id': str(self.id) if self.id else None,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'tags': self.tags or [],
            'rating': self.rating,
            'rating_sum': self.rating_sum,
            'rating_count': self.rating_count,
            'created_at': self.created_at.strftime('%Y-%m-%dT%H:%M:%SZ') if self.created_at else None,
        }
        if include_content:
            data['json_content'] = self.json_content
        return data

    def __repr__(self):
        return f'<OrchTemplate {self.id} name="{self.name}" category="{self.category}">'
