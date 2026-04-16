"""Webhook and WebhookLog models for the event/webhook system."""
import uuid

from dimensigon.utils.typos import UUID, UtcDateTime
from dimensigon.utils.helpers import get_now
from dimensigon.web import db


class Webhook(db.Model):
    __tablename__ = 'D_webhook'

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(256))
    url = db.Column(db.String(2048), nullable=False)
    event_types = db.Column(db.JSON, default=list)
    headers = db.Column(db.JSON, default=dict)
    retry_max = db.Column(db.Integer, default=5)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(UtcDateTime, default=get_now)

    logs = db.relationship('WebhookLog', backref='webhook', lazy='dynamic',
                           cascade='all, delete-orphan')

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'event_types': self.event_types or [],
            'headers': self.headers or {},
            'retry_max': self.retry_max,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WebhookLog(db.Model):
    __tablename__ = 'D_webhook_log'

    id = db.Column(UUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = db.Column(UUID, db.ForeignKey('D_webhook.id'), nullable=False)
    event_type = db.Column(db.String(256))
    status_code = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    attempt = db.Column(db.Integer)
    success = db.Column(db.Boolean)
    created_at = db.Column(UtcDateTime, default=get_now)

    def to_json(self):
        return {
            'id': self.id,
            'webhook_id': self.webhook_id,
            'event_type': self.event_type,
            'status_code': self.status_code,
            'response_body': self.response_body,
            'attempt': self.attempt,
            'success': self.success,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
