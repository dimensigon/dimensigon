"""Webhook dispatcher for the event/webhook system."""
import json
import logging
import threading
import time
import uuid

import requests
from flask import current_app

from dimensigon.utils.helpers import get_now

logger = logging.getLogger('dm.webhooks')


def dispatch_event(event_type, payload):
    """Query active webhooks matching event_type and dispatch HTTP POST to each in a background thread."""
    from dimensigon.web import db
    from dimensigon.domain.entities.webhook import Webhook

    try:
        app = current_app._get_current_object()
    except RuntimeError:
        logger.warning('No Flask application context available for webhook dispatch')
        return

    webhooks = db.session.execute(
        db.select(Webhook).where(Webhook.active == True)  # noqa: E712
    ).scalars().all()

    matching = []
    for wh in webhooks:
        event_types = wh.event_types or []
        if not event_types or event_type in event_types:
            matching.append({
                'id': wh.id,
                'url': wh.url,
                'headers': wh.headers or {},
                'retry_max': wh.retry_max or 5,
            })

    for wh_data in matching:
        t = threading.Thread(
            target=_deliver_webhook,
            args=(app, wh_data, event_type, payload),
            daemon=True,
        )
        t.start()


def _deliver_webhook(app, wh_data, event_type, payload):
    """Deliver a webhook with exponential backoff retries."""
    from dimensigon.web import db
    from dimensigon.domain.entities.webhook import WebhookLog

    webhook_id = wh_data['id']
    url = wh_data['url']
    headers = dict(wh_data.get('headers') or {})
    headers.setdefault('Content-Type', 'application/json')
    retry_max = wh_data.get('retry_max', 5)

    body = json.dumps({
        'event_type': event_type,
        'payload': payload,
    })

    for attempt in range(1, retry_max + 1):
        status_code = None
        response_body = None
        success = False

        try:
            resp = requests.post(url, data=body, headers=headers, timeout=10)
            status_code = resp.status_code
            response_body = resp.text[:4096] if resp.text else None
            success = 200 <= resp.status_code < 300
        except requests.RequestException as exc:
            status_code = 0
            response_body = str(exc)[:4096]
            success = False

        # Log the attempt
        try:
            with app.app_context():
                log_entry = WebhookLog(
                    id=str(uuid.uuid4()),
                    webhook_id=webhook_id,
                    event_type=event_type,
                    status_code=status_code,
                    response_body=response_body,
                    attempt=attempt,
                    success=success,
                    created_at=get_now(),
                )
                db.session.add(log_entry)
                db.session.commit()
        except Exception as log_exc:
            logger.error('Failed to log webhook delivery: %s', log_exc)

        if success:
            logger.info('Webhook %s delivered to %s on attempt %d', webhook_id, url, attempt)
            return

        if attempt < retry_max:
            backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s, 8s, 16s
            logger.warning(
                'Webhook %s delivery to %s failed (attempt %d/%d, status=%s), retrying in %ds',
                webhook_id, url, attempt, retry_max, status_code, backoff,
            )
            time.sleep(backoff)

    logger.error('Webhook %s delivery to %s exhausted all %d retries', webhook_id, url, retry_max)
