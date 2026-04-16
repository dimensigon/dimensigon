"""Notification Python action generators - 10 seeds for Slack, email, Telegram, PagerDuty, etc."""

from examples.generators.base_generator import PythonActionGenerator


class NotificationsGenerator(PythonActionGenerator):
    category = "python.notifications"
    subcategory = "notifications"

    def seeds(self):
        return [
            {
                'name': 'slack-webhook',
                'template': {
                    'name': 'Send Slack notification',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'webhook_url = "{{input.webhook_url}}"\n'
                        'channel = "{{input.channel}}"\n'
                        'message = "{{input.message}}"\n'
                        'severity = "{{input.severity}}" or "info"\n\n'
                        'color_map = {{"info": "#36a64f", "warning": "#ffcc00", "critical": "#ff0000"}}\n'
                        'payload = {{\n'
                        '    "channel": channel,\n'
                        '    "attachments": [{{\n'
                        '        "color": color_map.get(severity, "#36a64f"),\n'
                        '        "title": f"[{{severity.upper()}}] Alert",\n'
                        '        "text": message,\n'
                        '        "footer": "Dimensigon Automation",\n'
                        '    }}],\n'
                        '}}\n\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(webhook_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    print(json.dumps({{"status": "sent", "channel": channel}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'webhook_url': {'type': 'string', 'description': 'Slack incoming webhook URL'},
                            'channel': {'type': 'string', 'description': 'Slack channel name'},
                            'message': {'type': 'string', 'description': 'Message text to send'},
                            'severity': {'type': 'string', 'description': 'Severity level: info, warning, critical'},
                        },
                        'required': ['webhook_url', 'channel', 'message'],
                    },
                },
                'params': {'severity': ['info', 'warning', 'critical']},
                'prompts': [
                    'Create a Python action to send a {severity} notification to Slack',
                    'Python script that posts a {severity}-level alert to a Slack channel via webhook',
                ],
                'explanation': 'Python action that sends a {severity}-level notification to a Slack channel using an incoming webhook with color-coded severity.',
            },
            {
                'name': 'email-smtp',
                'template': {
                    'name': 'Send email via SMTP',
                    'action_type': 'PYTHON',
                    'code': (
                        'import smtplib\n'
                        'import json\n'
                        'import sys\n'
                        'from email.mime.text import MIMEText\n'
                        'from email.mime.multipart import MIMEMultipart\n\n'
                        'smtp_host = "{{input.smtp_host}}"\n'
                        'smtp_port = int("{{input.smtp_port}}" or "587")\n'
                        'username = "{{input.username}}"\n'
                        'password = "{{input.password}}"\n'
                        'sender = "{{input.from_addr}}"\n'
                        'recipient = "{{input.to_addr}}"\n'
                        'subject = "{{input.subject}}"\n'
                        'body = "{{input.body}}"\n\n'
                        'msg = MIMEMultipart()\n'
                        'msg["From"] = sender\n'
                        'msg["To"] = recipient\n'
                        'msg["Subject"] = subject\n'
                        'msg.attach(MIMEText(body, "plain"))\n\n'
                        'try:\n'
                        '    with smtplib.SMTP(smtp_host, smtp_port) as server:\n'
                        '        server.ehlo()\n'
                        '        server.starttls()\n'
                        '        server.login(username, password)\n'
                        '        server.sendmail(sender, [recipient], msg.as_string())\n'
                        '    print(json.dumps({{"status": "sent", "to": recipient, "subject": subject}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'smtp_host': {'type': 'string', 'description': 'SMTP server hostname'},
                            'smtp_port': {'type': 'string', 'description': 'SMTP server port (default 587)'},
                            'username': {'type': 'string', 'description': 'SMTP username'},
                            'password': {'type': 'string', 'description': 'SMTP password'},
                            'from_addr': {'type': 'string', 'description': 'Sender email address'},
                            'to_addr': {'type': 'string', 'description': 'Recipient email address'},
                            'subject': {'type': 'string', 'description': 'Email subject'},
                            'body': {'type': 'string', 'description': 'Email body text'},
                        },
                        'required': ['smtp_host', 'username', 'password', 'from_addr', 'to_addr', 'subject', 'body'],
                    },
                },
                'params': {'smtp_provider': ['gmail', 'ses', 'sendgrid', 'mailgun', 'postfix']},
                'prompts': [
                    'Create a Python action to send an email via {smtp_provider} SMTP',
                    'Python script that sends a notification email through {smtp_provider}',
                ],
                'explanation': 'Python action that sends an email notification via {smtp_provider} SMTP with TLS encryption.',
            },
            {
                'name': 'telegram-message',
                'template': {
                    'name': 'Send Telegram bot message',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.parse\n'
                        'import sys\n\n'
                        'bot_token = "{{input.bot_token}}"\n'
                        'chat_id = "{{input.chat_id}}"\n'
                        'message = "{{input.message}}"\n'
                        'parse_mode = "{{input.parse_mode}}" or "Markdown"\n\n'
                        'url = f"https://api.telegram.org/bot{{bot_token}}/sendMessage"\n'
                        'data = urllib.parse.urlencode({{\n'
                        '    "chat_id": chat_id,\n'
                        '    "text": message,\n'
                        '    "parse_mode": parse_mode,\n'
                        '}}).encode("utf-8")\n\n'
                        'req = urllib.request.Request(url, data=data, method="POST")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    if result.get("ok"):\n'
                        '        print(json.dumps({{"status": "sent", "message_id": result["result"]["message_id"]}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "description": result.get("description")}}))\n'
                        '        sys.exit(1)\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'bot_token': {'type': 'string', 'description': 'Telegram bot API token'},
                            'chat_id': {'type': 'string', 'description': 'Telegram chat or group ID'},
                            'message': {'type': 'string', 'description': 'Message text to send'},
                            'parse_mode': {'type': 'string', 'description': 'Parse mode: Markdown or HTML'},
                        },
                        'required': ['bot_token', 'chat_id', 'message'],
                    },
                },
                'params': {'parse_mode': ['Markdown', 'HTML']},
                'prompts': [
                    'Create a Python action to send a Telegram bot message in {parse_mode} format',
                    'Python script that sends a notification via Telegram bot using {parse_mode}',
                ],
                'explanation': 'Python action that sends a {parse_mode}-formatted message via Telegram Bot API to a specified chat.',
            },
            {
                'name': 'pagerduty-alert',
                'template': {
                    'name': 'PagerDuty alert trigger',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'routing_key = "{{input.routing_key}}"\n'
                        'summary = "{{input.summary}}"\n'
                        'severity = "{{input.severity}}" or "error"\n'
                        'source = "{{input.source}}" or "dimensigon"\n'
                        'component = "{{input.component}}"\n\n'
                        'payload = {{\n'
                        '    "routing_key": routing_key,\n'
                        '    "event_action": "trigger",\n'
                        '    "payload": {{\n'
                        '        "summary": summary,\n'
                        '        "severity": severity,\n'
                        '        "source": source,\n'
                        '        "component": component,\n'
                        '    }},\n'
                        '}}\n\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'url = "https://events.pagerduty.com/v2/enqueue"\n'
                        'req = urllib.request.Request(url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": result.get("status"), "dedup_key": result.get("dedup_key")}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'routing_key': {'type': 'string', 'description': 'PagerDuty Events API v2 routing key'},
                            'summary': {'type': 'string', 'description': 'Alert summary text'},
                            'severity': {'type': 'string', 'description': 'Severity: critical, error, warning, info'},
                            'source': {'type': 'string', 'description': 'Source of the alert'},
                            'component': {'type': 'string', 'description': 'Affected component'},
                        },
                        'required': ['routing_key', 'summary'],
                    },
                },
                'params': {'severity': ['critical', 'error', 'warning', 'info']},
                'prompts': [
                    'Create a Python action to trigger a {severity} PagerDuty alert',
                    'Python script that sends a {severity}-level incident to PagerDuty',
                ],
                'explanation': 'Python action that triggers a {severity}-level PagerDuty alert using Events API v2.',
            },
            {
                'name': 'discord-webhook',
                'template': {
                    'name': 'Send Discord webhook message',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'webhook_url = "{{input.webhook_url}}"\n'
                        'title = "{{input.title}}"\n'
                        'message = "{{input.message}}"\n'
                        'color = int("{{input.color}}" or "3066993")\n\n'
                        'payload = {{\n'
                        '    "embeds": [{{\n'
                        '        "title": title,\n'
                        '        "description": message,\n'
                        '        "color": color,\n'
                        '        "footer": {{"text": "Dimensigon Automation"}},\n'
                        '    }}],\n'
                        '}}\n\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(webhook_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    print(json.dumps({{"status": "sent", "code": resp.getcode()}}))\n'
                        'except urllib.error.HTTPError as e:\n'
                        '    if e.code == 204:\n'
                        '        print(json.dumps({{"status": "sent", "code": 204}}))\n'
                        '    else:\n'
                        '        print(json.dumps({{"status": "error", "code": e.code}}))\n'
                        '        sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'webhook_url': {'type': 'string', 'description': 'Discord webhook URL'},
                            'title': {'type': 'string', 'description': 'Embed title'},
                            'message': {'type': 'string', 'description': 'Embed description/message'},
                            'color': {'type': 'string', 'description': 'Embed color as decimal integer (default green)'},
                        },
                        'required': ['webhook_url', 'title', 'message'],
                    },
                },
                'params': {'notification_type': ['alert', 'deployment', 'status', 'report']},
                'prompts': [
                    'Create a Python action to send a {notification_type} notification to Discord',
                    'Python script that posts a {notification_type} message to Discord via webhook',
                ],
                'explanation': 'Python action that sends a {notification_type} notification to Discord using a webhook with embedded message formatting.',
            },
            {
                'name': 'sms-twilio',
                'template': {
                    'name': 'Send SMS via Twilio',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.parse\n'
                        'import base64\n'
                        'import sys\n\n'
                        'account_sid = "{{input.account_sid}}"\n'
                        'auth_token = "{{input.auth_token}}"\n'
                        'from_number = "{{input.from_number}}"\n'
                        'to_number = "{{input.to_number}}"\n'
                        'message = "{{input.message}}"\n\n'
                        'url = f"https://api.twilio.com/2010-04-01/Accounts/{{account_sid}}/Messages.json"\n'
                        'data = urllib.parse.urlencode({{\n'
                        '    "From": from_number,\n'
                        '    "To": to_number,\n'
                        '    "Body": message,\n'
                        '}}).encode("utf-8")\n\n'
                        'credentials = base64.b64encode(f"{{account_sid}}:{{auth_token}}".encode()).decode()\n'
                        'req = urllib.request.Request(url, data=data, method="POST")\n'
                        'req.add_header("Authorization", "Basic " + credentials)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "sent", "sid": result.get("sid"), "to": to_number}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'account_sid': {'type': 'string', 'description': 'Twilio account SID'},
                            'auth_token': {'type': 'string', 'description': 'Twilio auth token'},
                            'from_number': {'type': 'string', 'description': 'Twilio phone number (sender)'},
                            'to_number': {'type': 'string', 'description': 'Recipient phone number'},
                            'message': {'type': 'string', 'description': 'SMS message text'},
                        },
                        'required': ['account_sid', 'auth_token', 'from_number', 'to_number', 'message'],
                    },
                },
                'params': {'urgency': ['low', 'medium', 'high', 'critical']},
                'prompts': [
                    'Create a Python action to send a {urgency}-priority SMS via Twilio',
                    'Python script that sends an SMS notification through Twilio API',
                ],
                'explanation': 'Python action that sends an SMS message via the Twilio REST API with basic authentication.',
            },
            {
                'name': 'teams-webhook',
                'template': {
                    'name': 'Send Microsoft Teams message',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'webhook_url = "{{input.webhook_url}}"\n'
                        'title = "{{input.title}}"\n'
                        'message = "{{input.message}}"\n'
                        'severity = "{{input.severity}}" or "info"\n\n'
                        'color_map = {{"info": "0076D7", "warning": "FFA500", "critical": "FF0000", "success": "00FF00"}}\n'
                        'payload = {{\n'
                        '    "@type": "MessageCard",\n'
                        '    "@context": "http://schema.org/extensions",\n'
                        '    "themeColor": color_map.get(severity, "0076D7"),\n'
                        '    "summary": title,\n'
                        '    "sections": [{{\n'
                        '        "activityTitle": title,\n'
                        '        "activitySubtitle": f"Severity: {{severity}}",\n'
                        '        "text": message,\n'
                        '    }}],\n'
                        '}}\n\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'req = urllib.request.Request(webhook_url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    print(json.dumps({{"status": "sent", "severity": severity}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'webhook_url': {'type': 'string', 'description': 'Microsoft Teams webhook URL'},
                            'title': {'type': 'string', 'description': 'Card title'},
                            'message': {'type': 'string', 'description': 'Message body text'},
                            'severity': {'type': 'string', 'description': 'Severity: info, warning, critical, success'},
                        },
                        'required': ['webhook_url', 'title', 'message'],
                    },
                },
                'params': {'severity': ['info', 'warning', 'critical', 'success']},
                'prompts': [
                    'Create a Python action to send a {severity} alert to Microsoft Teams',
                    'Python script that posts a {severity} notification to Teams channel',
                ],
                'explanation': 'Python action that sends a {severity}-level MessageCard notification to Microsoft Teams via incoming webhook.',
            },
            {
                'name': 'opsgenie-alert',
                'template': {
                    'name': 'Create Opsgenie alert',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import sys\n\n'
                        'api_key = "{{input.api_key}}"\n'
                        'message = "{{input.message}}"\n'
                        'priority = "{{input.priority}}" or "P3"\n'
                        'description = "{{input.description}}"\n'
                        'alias = "{{input.alias}}"\n\n'
                        'payload = {{\n'
                        '    "message": message,\n'
                        '    "priority": priority,\n'
                        '    "description": description,\n'
                        '}}\n'
                        'if alias:\n'
                        '    payload["alias"] = alias\n\n'
                        'data = json.dumps(payload).encode("utf-8")\n'
                        'url = "https://api.opsgenie.com/v2/alerts"\n'
                        'req = urllib.request.Request(url, data=data, method="POST")\n'
                        'req.add_header("Content-Type", "application/json")\n'
                        'req.add_header("Authorization", "GenieKey " + api_key)\n'
                        'try:\n'
                        '    resp = urllib.request.urlopen(req, timeout=15)\n'
                        '    result = json.loads(resp.read().decode())\n'
                        '    print(json.dumps({{"status": "created", "request_id": result.get("requestId")}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'api_key': {'type': 'string', 'description': 'Opsgenie API key'},
                            'message': {'type': 'string', 'description': 'Alert message'},
                            'priority': {'type': 'string', 'description': 'Priority: P1-P5 (default P3)'},
                            'description': {'type': 'string', 'description': 'Alert description'},
                            'alias': {'type': 'string', 'description': 'Alert alias for dedup (optional)'},
                        },
                        'required': ['api_key', 'message'],
                    },
                },
                'params': {'priority': ['P1', 'P2', 'P3', 'P4', 'P5']},
                'prompts': [
                    'Create a Python action to create a {priority} Opsgenie alert',
                    'Python script that triggers a {priority}-priority alert in Opsgenie',
                ],
                'explanation': 'Python action that creates an Opsgenie alert with {priority} priority using the Opsgenie REST API v2.',
            },
            {
                'name': 'generic-webhook-retry',
                'template': {
                    'name': 'Generic webhook with retry',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import urllib.request\n'
                        'import urllib.error\n'
                        'import time\n'
                        'import sys\n\n'
                        'url = "{{input.url}}"\n'
                        'payload_str = \'{{input.payload}}\'\n'
                        'max_retries = int("{{input.max_retries}}" or "3")\n'
                        'headers_str = \'{{input.headers}}\' or "{{}}"\n\n'
                        'payload = json.loads(payload_str)\n'
                        'headers = json.loads(headers_str)\n'
                        'data = json.dumps(payload).encode("utf-8")\n\n'
                        'for attempt in range(1, max_retries + 1):\n'
                        '    req = urllib.request.Request(url, data=data, method="POST")\n'
                        '    req.add_header("Content-Type", "application/json")\n'
                        '    for k, v in headers.items():\n'
                        '        req.add_header(k, v)\n'
                        '    try:\n'
                        '        resp = urllib.request.urlopen(req, timeout=15)\n'
                        '        code = resp.getcode()\n'
                        '        if code < 300:\n'
                        '            print(json.dumps({{"status": "sent", "code": code, "attempt": attempt}}))\n'
                        '            sys.exit(0)\n'
                        '    except urllib.error.HTTPError as e:\n'
                        '        if attempt == max_retries:\n'
                        '            print(json.dumps({{"status": "failed", "code": e.code, "attempts": attempt}}))\n'
                        '            sys.exit(1)\n'
                        '    except Exception as e:\n'
                        '        if attempt == max_retries:\n'
                        '            print(json.dumps({{"status": "error", "message": str(e), "attempts": attempt}}))\n'
                        '            sys.exit(1)\n'
                        '    time.sleep(2 ** attempt)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'url': {'type': 'string', 'description': 'Webhook URL'},
                            'payload': {'type': 'string', 'description': 'JSON payload string'},
                            'max_retries': {'type': 'string', 'description': 'Max retry attempts (default 3)'},
                            'headers': {'type': 'string', 'description': 'JSON string of extra headers (optional)'},
                        },
                        'required': ['url', 'payload'],
                    },
                },
                'params': {'target': ['monitoring', 'alerting', 'logging', 'ticketing']},
                'prompts': [
                    'Create a Python action to send a webhook to a {target} system with retry',
                    'Python script for posting to a {target} webhook with exponential backoff',
                ],
                'explanation': 'Python action that sends a webhook POST request to a {target} system with exponential backoff retry on failure.',
            },
            {
                'name': 'log-notification',
                'template': {
                    'name': 'Log notification to file',
                    'action_type': 'PYTHON',
                    'code': (
                        'import json\n'
                        'import os\n'
                        'import sys\n'
                        'from datetime import datetime\n\n'
                        'log_file = "{{input.log_file}}"\n'
                        'level = "{{input.level}}" or "INFO"\n'
                        'message = "{{input.message}}"\n'
                        'source = "{{input.source}}" or "dimensigon"\n\n'
                        'log_dir = os.path.dirname(log_file)\n'
                        'if log_dir and not os.path.isdir(log_dir):\n'
                        '    os.makedirs(log_dir, exist_ok=True)\n\n'
                        'timestamp = datetime.utcnow().isoformat() + "Z"\n'
                        'entry = {{\n'
                        '    "timestamp": timestamp,\n'
                        '    "level": level.upper(),\n'
                        '    "source": source,\n'
                        '    "message": message,\n'
                        '}}\n\n'
                        'try:\n'
                        '    with open(log_file, "a") as f:\n'
                        '        f.write(json.dumps(entry) + "\\n")\n'
                        '    print(json.dumps({{"status": "logged", "file": log_file, "level": level}}))\n'
                        'except Exception as e:\n'
                        '    print(json.dumps({{"status": "error", "message": str(e)}}))\n'
                        '    sys.exit(1)\n'
                    ),
                    'expected_rc': 0,
                    'schema': {
                        'input': {
                            'log_file': {'type': 'string', 'description': 'Path to log file'},
                            'level': {'type': 'string', 'description': 'Log level: INFO, WARNING, ERROR, CRITICAL'},
                            'message': {'type': 'string', 'description': 'Log message'},
                            'source': {'type': 'string', 'description': 'Source identifier (optional)'},
                        },
                        'required': ['log_file', 'message'],
                    },
                },
                'params': {'level': ['INFO', 'WARNING', 'ERROR', 'CRITICAL']},
                'prompts': [
                    'Create a Python action to log a {level} notification to a file',
                    'Python script that appends a {level}-level JSON log entry to a file',
                ],
                'explanation': 'Python action that appends a structured JSON {level}-level log entry to a notification log file.',
            },
        ]


def get_generators():
    return [NotificationsGenerator()]
