"""Webhook dispatcher for the event/webhook system."""
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import threading
import time
import uuid
from urllib.parse import urlparse

import requests
from flask import current_app

from dimensigon.utils.helpers import get_now

logger = logging.getLogger('dm.webhooks')


def _is_public_host(host):
    """True only if every resolved address of ``host`` is a global/public IP.
    Blocks loopback, RFC1918 private, link-local (incl. 169.254.169.254 cloud
    metadata), reserved, multicast and unspecified ranges. Resolution happens
    at call time so it also blocks DNS-rebinding at send time."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False
    return True


def _validate_webhook_url(url):
    """Return an error string if ``url`` is unsafe to call, else None."""
    parsed = urlparse(url or '')
    if parsed.scheme != 'https':
        return "webhook url must use https"
    if not parsed.hostname:
        return "webhook url missing host"
    if not _is_public_host(parsed.hostname):
        return "webhook host resolves to a private/loopback/link-local address"
    return None


def _sign_payload(body):
    """Compute the X-DM-Signature HMAC-SHA256 header value for ``body``.
    Returns None when no signing secret is configured."""
    secret = os.environ.get('DM_WEBHOOK_SIGNING_SECRET')
    if not secret:
        return None
    mac = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256)
    return 'sha256=' + mac.hexdigest()


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

    # SSRF guard: reject internal / non-https destinations before any request.
    url_error = _validate_webhook_url(url)
    if url_error:
        logger.error('Webhook %s blocked: %s (url=%s)', webhook_id, url_error, url)
        try:
            with app.app_context():
                db.session.add(WebhookLog(
                    id=str(uuid.uuid4()), webhook_id=webhook_id, event_type=event_type,
                    status_code=0, response_body=('blocked: ' + url_error)[:4096],
                    attempt=1, success=False, created_at=get_now(),
                ))
                db.session.commit()
        except Exception as log_exc:
            logger.error('Failed to log blocked webhook: %s', log_exc)
        return

    # Sign the payload so receivers can verify authenticity (HMAC-SHA256).
    signature = _sign_payload(body)
    if signature:
        headers['X-DM-Signature'] = signature

    for attempt in range(1, retry_max + 1):
        status_code = None
        response_body = None
        success = False

        try:
            resp = requests.post(url, data=body, headers=headers, timeout=10,
                                 allow_redirects=False)
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
