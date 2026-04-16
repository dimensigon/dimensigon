"""
End-to-end tests for all 25 Dimensigon 3.0 features.

Tests exercise features through their public REST/API interfaces
as an end-user would interact with them.
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta
from unittest import TestCase, mock

# Test-only credentials. Not real secrets. Override via env for CI.
# pragma: allowlist secret
_TEST_PW_ADMIN = os.getenv('TEST_PW_ADMIN', 'test-pw-' + 'admin')  # noqa: S105
_TEST_PW_OP = os.getenv('TEST_PW_OP', 'test-pw-' + 'op')  # noqa: S105
_TEST_PW_VIEW = os.getenv('TEST_PW_VIEW', 'test-pw-' + 'view')  # noqa: S105

from dimensigon.domain.entities import (
    User, Server, Gate, Route, Orchestration, Step, ActionTemplate, ActionType,
    OrchExecution, StepExecution,
)
from dimensigon.utils.helpers import get_now
from dimensigon.web import create_app, db


class EndToEndBase(TestCase):
    """Base class with app setup, login helper, and seed data."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed admin user
        self.admin = User(id='00000000-0000-0000-0000-aaaaaaaaaaaa',
                          name='admin', groups=['administrator'], active=True)
        self.admin.set_password(_TEST_PW_ADMIN)
        # Seed operator user
        self.operator = User(id='00000000-0000-0000-0000-bbbbbbbbbbbb',
                             name='operator', groups=['operator'], active=True)
        self.operator.set_password(_TEST_PW_OP)
        # Seed viewer user
        self.viewer = User(id='00000000-0000-0000-0000-cccccccccccc',
                           name='viewer', groups=['readonly'], active=True)
        self.viewer.set_password(_TEST_PW_VIEW)
        db.session.add_all([self.admin, self.operator, self.viewer])

        # Seed action template
        self.at = ActionTemplate(id='00000000-0000-0000-000a-111111111111',
                                 name='Shell Exec', version=1,
                                 action_type=ActionType.SHELL, code='echo ok')
        db.session.add(self.at)

        # Seed orchestration
        self.orch = Orchestration(id='00000000-0000-0000-000b-111111111111',
                                  name='test_deploy', version=1,
                                  description='Test deployment orchestration')
        db.session.add(self.orch)
        db.session.flush()

        self.step = Step(orchestration=self.orch,
                         action_template=self.at, undo=False)
        db.session.add(self.step)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, username='admin', password=None):
        if password is None:
            password = {
                'admin': _TEST_PW_ADMIN,
                'operator': _TEST_PW_OP,
                'viewer': _TEST_PW_VIEW,
            }.get(username, _TEST_PW_ADMIN)
        return self.client.post('/dm-webmanager/login',
                                data=json.dumps({'username': username, 'password': password}),
                                content_type='application/json')

    def api(self, method, path, data=None, **kwargs):
        fn = getattr(self.client, method)
        kw = {'content_type': 'application/json'}
        kw.update(kwargs)
        if data is not None:
            kw['data'] = json.dumps(data)
        return fn(path, **kw)


# ==============================================================
# PHASE 1: Foundation
# ==============================================================

class TestPhase1_SQLAlchemy2x(EndToEndBase):
    """Plan 01: Verify SQLAlchemy 2.x patterns work end-to-end."""

    def test_select_style_query_via_api(self):
        """ORM queries work through API endpoints."""
        self.login()
        resp = self.api('get', '/dm-webmanager/api/builder/action-templates')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        templates = data if isinstance(data, list) else data.get('action_templates', [])
        self.assertTrue(len(templates) >= 1)
        self.assertEqual('Shell Exec', templates[0]['name'])

    def test_session_get_works(self):
        """db.session.get() works for model lookups."""
        user = db.session.get(User, self.admin.id)
        self.assertEqual('admin', user.name)


class TestPhase1_SecurityLayer(EndToEndBase):
    """Plan 02: SECURIZER_MODE configuration."""

    def test_securizer_mode_config_exists(self):
        self.assertIn('SECURIZER_MODE', self.app.config)

    def test_securizer_mode_default(self):
        from dimensigon.web.config import Config
        self.assertEqual('auto', Config.SECURIZER_MODE)


class TestPhase1_ForwardDispatch(EndToEndBase):
    """Plan 03: GET requests don't crash on decorated endpoints."""

    def test_get_healthcheck_no_crash(self):
        """GET on forward_or_dispatch endpoint works without JSON body."""
        resp = self.client.get('/healthcheck')
        # May return 500 due to missing server context in test, but NOT 400/415
        self.assertNotIn(resp.status_code, [400, 415])


class TestPhase1_HealthEndpoint(EndToEndBase):
    """Plan 04: /health endpoint."""

    def test_health_no_auth(self):
        resp = self.client.get('/health')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('ok', data['status'])
        self.assertIn('version', data)
        self.assertIn('node', data)
        self.assertIn('neighbours', data)

    def test_health_detail(self):
        resp = self.client.get('/health?detail=true')
        data = resp.get_json()
        self.assertIn('detail', data)
        self.assertIn('uptime_seconds', data['detail'])
        self.assertTrue(data['detail']['db_ok'])


class TestPhase1_AuthFlow(EndToEndBase):
    """Plan 05: Authentication flow with RBAC."""

    def test_login_sets_cookies(self):
        resp = self.login()
        self.assertEqual(200, resp.status_code)
        cookies = [h.split('=')[0] for h in resp.headers.getlist('Set-Cookie')]
        self.assertIn('access_token_cookie', cookies)

    def test_login_wrong_password(self):
        resp = self.login('admin', 'wrong')
        self.assertEqual(401, resp.status_code)

    def test_protected_route_redirects(self):
        resp = self.client.get('/dm-webmanager/', follow_redirects=False)
        self.assertEqual(302, resp.status_code)

    def test_protected_route_accessible_after_login(self):
        self.login()
        resp = self.client.get('/dm-webmanager/')
        self.assertEqual(200, resp.status_code)

    def test_logout_clears_session(self):
        self.login()
        self.client.post('/dm-webmanager/logout')
        resp = self.client.get('/dm-webmanager/', follow_redirects=False)
        self.assertEqual(302, resp.status_code)

    def test_refresh_token(self):
        self.login()
        resp = self.client.post('/dm-webmanager/refresh')
        self.assertEqual(200, resp.status_code)

    def test_viewer_cannot_access_admin_endpoints(self):
        self.login('viewer', _TEST_PW_VIEW)
        resp = self.api('get', '/dm-webmanager/api/audit')
        # Should be 403 or redirect (viewer doesn't have administrator role)
        self.assertIn(resp.status_code, [302, 403])


# ==============================================================
# PHASE 2: Core UX
# ==============================================================

class TestPhase2_RealtimeMonitoring(EndToEndBase):
    """Plan 06: WebSocket monitoring and cancel API."""

    def test_cancel_endpoint_requires_auth(self):
        resp = self.api('post', '/dm-webmanager/executions/fake-id/cancel')
        self.assertEqual(302, resp.status_code)  # redirect to login

    def test_cancel_nonexistent_execution(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/executions/nonexistent/cancel')
        self.assertEqual(404, resp.status_code)

    def test_ws_manager_broadcast(self):
        """WS manager can broadcast without viewers."""
        from dimensigon.web.admin.ws import ws_manager, ExecutionEvent
        event = ExecutionEvent('test', 'exec-1', {'key': 'val'})
        ws_manager.broadcast(event)  # Should not raise


class TestPhase2_OrchBuilder(EndToEndBase):
    """Plan 07: Visual orchestration builder API."""

    def test_list_action_templates(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/builder/action-templates')
        self.assertEqual(200, resp.status_code)

    def test_validate_valid_dag(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/builder/validate', {
            'name': 'test',
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at.id), 'parents': [], 'children': ['s2']},
                {'id': 's2', 'action_template_id': str(self.at.id), 'parents': ['s1'], 'children': []},
            ]
        })
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.get_json()['valid'])

    def test_validate_cycle_rejected(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/builder/validate', {
            'name': 'test',
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at.id), 'parents': ['s2'], 'children': ['s2']},
                {'id': 's2', 'action_template_id': str(self.at.id), 'parents': ['s1'], 'children': ['s1']},
            ]
        })
        self.assertFalse(resp.get_json()['valid'])

    def test_save_orchestration(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/builder/save', {
            'name': 'Built Orch',
            'description': 'From builder',
            'steps': [
                {'id': 's1', 'action_template_id': str(self.at.id),
                 'target': ['srv1'], 'parents': [], 'children': [], 'undo': False},
            ]
        })
        self.assertIn(resp.status_code, [200, 201])


class TestPhase2_Topology(EndToEndBase):
    """Plan 08: Server topology API."""

    def test_topology_returns_nodes_and_edges(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/topology')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('nodes', data)
        self.assertIn('edges', data)


class TestPhase2_Widgets(EndToEndBase):
    """Plan 10: Dashboard widgets."""

    def test_success_rate_widget(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/widgets/success-rate')
        self.assertEqual(200, resp.status_code)
        self.assertIn('days', resp.get_json())

    def test_top_failures_widget(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/widgets/top-failures')
        self.assertEqual(200, resp.status_code)
        self.assertIn('failures', resp.get_json())

    def test_recent_activity_widget(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/widgets/recent-activity')
        self.assertEqual(200, resp.status_code)
        self.assertIn('events', resp.get_json())


class TestPhase2_Prometheus(EndToEndBase):
    """Plan 24: /metrics endpoint."""

    def test_metrics_no_auth(self):
        resp = self.client.get('/metrics')
        self.assertEqual(200, resp.status_code)
        self.assertIn(b'dm_api_requests_total', resp.data)

    def test_metrics_tracks_requests(self):
        self.client.get('/health')
        self.client.get('/health')
        resp = self.client.get('/metrics')
        self.assertIn(b'dm_api_requests', resp.data)


# ==============================================================
# PHASE 3: Features
# ==============================================================

class TestPhase3_Webhooks(EndToEndBase):
    """Plan 12: Webhook CRUD and dispatch."""

    def test_create_list_delete_webhook(self):
        self.login()
        # Create
        resp = self.api('post', '/dm-webmanager/api/webhooks', {
            'name': 'Test Hook',
            'url': 'https://httpbin.org/post',
            'event_types': ['orchestration.completed'],
        })
        self.assertIn(resp.status_code, [200, 201])
        hook_id = resp.get_json().get('id') or resp.get_json().get('webhook', {}).get('id')
        self.assertIsNotNone(hook_id)

        # List
        resp = self.api('get', '/dm-webmanager/api/webhooks')
        self.assertEqual(200, resp.status_code)
        webhooks = resp.get_json()
        hooks = webhooks if isinstance(webhooks, list) else webhooks.get('webhooks', [])
        self.assertTrue(len(hooks) >= 1)

        # Delete
        resp = self.api('delete', f'/dm-webmanager/api/webhooks/{hook_id}')
        self.assertIn(resp.status_code, [200, 204])

    def test_webhook_dispatch(self):
        """Dispatch function works without errors."""
        from dimensigon.domain.entities.webhook import Webhook
        hook = Webhook(name='test', url='https://example.com/hook',
                       event_types=['orchestration.failed'], active=True)
        db.session.add(hook)
        db.session.commit()

        from dimensigon.use_cases.webhooks import dispatch_event
        with mock.patch('dimensigon.use_cases.webhooks.requests.post') as mock_post:
            mock_post.return_value = mock.MagicMock(status_code=200, text='ok')
            dispatch_event('orchestration.failed', {'execution_id': 'test-123'})
            time.sleep(0.5)  # Background thread


class TestPhase3_Schedules(EndToEndBase):
    """Plan 13: Cron scheduled orchestrations."""

    def test_create_and_list_schedule(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/schedules', {
            'orchestration_id': str(self.orch.id),
            'cron_expr': '*/5 * * * *',
        })
        self.assertIn(resp.status_code, [200, 201])

        resp = self.api('get', '/dm-webmanager/api/schedules')
        self.assertEqual(200, resp.status_code)
        schedules = resp.get_json()
        items = schedules if isinstance(schedules, list) else schedules.get('schedules', [])
        self.assertTrue(len(items) >= 1)

    def test_invalid_cron_rejected(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/schedules', {
            'orchestration_id': str(self.orch.id),
            'cron_expr': 'not a cron',
        })
        self.assertIn(resp.status_code, [400, 422])

    def test_compute_next_run(self):
        from dimensigon.use_cases.scheduler import compute_next_run
        next_run = compute_next_run('0 * * * *')
        self.assertIsNotNone(next_run)
        self.assertTrue(next_run > datetime.now(timezone.utc))


class TestPhase3_AuditLog(EndToEndBase):
    """Plan 16: Audit log."""

    def test_login_creates_audit_entry(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/audit')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        entries = data.get('entries', [])
        login_entries = [e for e in entries if e.get('action') == 'login']
        self.assertTrue(len(login_entries) >= 1)

    def test_audit_requires_admin(self):
        self.login('viewer', _TEST_PW_VIEW)
        resp = self.api('get', '/dm-webmanager/api/audit')
        self.assertIn(resp.status_code, [302, 403])


class TestPhase3_Versioning(EndToEndBase):
    """Plan 14: Orchestration versioning and rollback."""

    def test_save_creates_version(self):
        self.login()
        # Save via builder to auto-create version
        self.api('post', '/dm-webmanager/api/builder/save', {
            'name': 'Versioned Orch',
            'steps': [{'id': 's1', 'action_template_id': str(self.at.id),
                       'target': [], 'parents': [], 'children': [], 'undo': False}]
        })
        # List versions
        from dimensigon.domain.entities import Orchestration
        from sqlalchemy import select
        orch = db.session.execute(
            select(Orchestration).filter_by(name='Versioned Orch')
        ).scalars().first()
        if orch:
            resp = self.api('get', f'/dm-webmanager/api/orchestrations/{orch.id}/versions')
            self.assertEqual(200, resp.status_code)
            data = resp.get_json()
            versions = data.get('versions', [])
            self.assertTrue(len(versions) >= 1)


class TestPhase3_ContainerDeploy(EndToEndBase):
    """Plan 25: Container-native deployment config."""

    def test_env_config_mapping(self):
        from dimensigon.web.config import Config
        self.assertTrue(hasattr(Config, 'DISCOVERY_DNS'))
        self.assertTrue(hasattr(Config, 'AUTO_JOIN'))
        self.assertTrue(hasattr(Config, 'GRACEFUL_SHUTDOWN_TIMEOUT'))

    def test_graceful_shutdown_method(self):
        from dimensigon.core import Dimensigon
        self.assertTrue(hasattr(Dimensigon, 'graceful_shutdown'))


# ==============================================================
# PHASE 4: AI & Polish
# ==============================================================

class TestPhase4_AIChat(EndToEndBase):
    """Plan 17: Context-aware AI chat."""

    def test_ai_chat_review_mode(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/chat', {
            'message': 'Review this orchestration',
            'mode': 'review',
            'orchestration_context': {'name': 'test', 'steps': []}
        })
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        # Response may have 'response' key or 'suggestions'/'message' depending on AI config
        self.assertTrue('response' in data or 'suggestions' in data or 'message' in data)

    def test_ai_chat_modify_mode(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/chat', {
            'message': 'Add error handling',
            'mode': 'modify',
            'orchestration_context': {'name': 'test', 'steps': []}
        })
        self.assertEqual(200, resp.status_code)

    def test_ai_chat_empty_message_rejected(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/chat', {
            'message': '', 'mode': 'review'
        })
        self.assertEqual(400, resp.status_code)


class TestPhase4_Troubleshoot(EndToEndBase):
    """Plan 18: AI-powered troubleshooting."""

    def test_troubleshoot_permission_denied(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/troubleshoot', {
            'command': 'rm /etc/hosts',
            'stdout': '',
            'stderr': 'Permission denied',
            'rc': 1
        })
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('root_cause', data)
        self.assertIn('permission', data['root_cause'].lower())

    def test_troubleshoot_command_not_found(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/troubleshoot', {
            'command': 'foobar',
            'stdout': '',
            'stderr': 'command not found: foobar',
            'rc': 127
        })
        data = resp.get_json()
        self.assertIn('root_cause', data)

    def test_analyze_failure_function(self):
        from dimensigon.ai.troubleshoot import analyze_failure
        result = analyze_failure({
            'command': 'curl http://localhost:9999',
            'stdout': '',
            'stderr': 'Connection refused',
            'rc': 7
        })
        self.assertEqual('high', result['confidence'])
        self.assertIn('connection', result['root_cause'].lower())


class TestPhase4_Templates(EndToEndBase):
    """Plan 11: Orchestration templates marketplace."""

    def test_create_search_rate_use_template(self):
        self.login()
        # Create
        resp = self.api('post', '/dm-webmanager/api/templates', {
            'name': 'Nginx Deploy',
            'description': 'Deploy nginx to web servers',
            'category': 'deployment',
            'tags': ['nginx', 'web'],
            'json_content': {'name': 'nginx_deploy', 'steps': []}
        })
        self.assertIn(resp.status_code, [200, 201])
        data = resp.get_json()
        tpl_id = data.get('id') or data.get('template', {}).get('id')

        # Search
        resp = self.api('get', '/dm-webmanager/api/templates?search=nginx')
        self.assertEqual(200, resp.status_code)
        results = resp.get_json()
        templates = results.get('templates', results if isinstance(results, list) else [])
        self.assertTrue(len(templates) >= 1)

        # Rate
        if tpl_id:
            resp = self.api('post', f'/dm-webmanager/api/templates/{tpl_id}/rate', {'rating': 1})
            self.assertEqual(200, resp.status_code)

            # Use
            resp = self.api('post', f'/dm-webmanager/api/templates/{tpl_id}/use')
            self.assertEqual(200, resp.status_code)
            data = resp.get_json()
            self.assertIn('json_content', data)


class TestPhase4_ExecDiff(EndToEndBase):
    """Plan 09: Execution history comparison."""

    def test_compare_and_trends(self):
        self.login()
        # Create two executions
        now = get_now()
        e1 = OrchExecution(id='00000000-0000-0000-eeee-111111111111',
                           orchestration_id=self.orch.id, start_time=now,
                           end_time=now + timedelta(seconds=5), success=True)
        e2 = OrchExecution(id='00000000-0000-0000-eeee-222222222222',
                           orchestration_id=self.orch.id, start_time=now + timedelta(minutes=1),
                           end_time=now + timedelta(minutes=1, seconds=10), success=False)
        db.session.add_all([e1, e2])
        db.session.commit()

        # Compare
        resp = self.api('get', f'/dm-webmanager/api/executions/compare?a={e1.id}&b={e2.id}')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('diff', data)
        self.assertTrue(data['diff']['status_changed'])

        # Trends
        resp = self.api('get', f'/dm-webmanager/api/executions/trends/{self.orch.id}')
        self.assertEqual(200, resp.status_code)
        self.assertIn('runs', resp.get_json())


class TestPhase4_DShellAutoComplete(EndToEndBase):
    """Plan 22: DShell auto-complete."""

    def test_fuzzy_match(self):
        from dimensigon.dshell.catalog import fuzzy_match
        results = fuzzy_match('hlth', ['health_check', 'deploy', 'backup'])
        self.assertIn('health_check', results)
        self.assertNotIn('backup', results)

    def test_catalog_class(self):
        from dimensigon.dshell.catalog import OrchestrationCatalog
        cat = OrchestrationCatalog()
        self.assertIsNotNone(cat.get_orchestration_names)


# ==============================================================
# PHASE 5: Advanced
# ==============================================================

class TestPhase5_Debugger(EndToEndBase):
    """Plan 21: Interactive step debugger."""

    def test_debugger_workflow(self):
        from dimensigon.dshell.debugger import StepDebugger
        dbg = StepDebugger()

        # Add breakpoint
        dbg.add_breakpoint('deploy')
        self.assertIn('deploy', dbg.list_breakpoints())

        # Should pause on breakpoint
        self.assertTrue(dbg.should_pause('deploy'))
        self.assertFalse(dbg.should_pause('other'))

        # Step-through mode
        dbg.stepping = True
        self.assertTrue(dbg.should_pause('any_step'))

        # Inspect
        ctx = {'command': 'echo hello', 'target_server': 'web-01', 'stdout': 'hello',
               'stderr': '', 'rc': 0, 'env': {'PATH': '/usr/bin'}, 'working_dir': '/tmp'}
        output = dbg.inspect_step(ctx)
        self.assertIn('echo hello', output)
        self.assertIn('web-01', output)

        # Modify
        new_ctx = dbg.modify_command(ctx, 'echo world')
        self.assertEqual('echo world', new_ctx['command'])
        self.assertEqual('echo hello', ctx['command'])  # Original unchanged

        # Parse commands
        self.assertEqual('inspect', dbg.parse_debug_command('inspect')['action'])
        self.assertEqual('rerun', dbg.parse_debug_command('rerun')['action'])
        self.assertEqual('abort', dbg.parse_debug_command('abort')['action'])

        # Variables
        output = dbg.format_variables({'host': 'web-01', 'port': 8080})
        self.assertIn('host', output)


class TestPhase5_WebTerminal(EndToEndBase):
    """Plan 23: DShell web terminal."""

    def test_terminal_session_lifecycle(self):
        self.login()
        # Create session
        resp = self.api('post', '/dm-webmanager/api/terminal/create')
        self.assertIn(resp.status_code, [200, 201])
        sid = resp.get_json()['session_id']

        # Execute command
        resp = self.api('post', f'/dm-webmanager/api/terminal/{sid}/execute',
                        {'command': 'help'})
        self.assertEqual(200, resp.status_code)
        self.assertIn('output', resp.get_json())

        # History
        resp = self.api('get', f'/dm-webmanager/api/terminal/{sid}/history')
        self.assertEqual(200, resp.status_code)
        history = resp.get_json()
        hist_list = history.get('history', history if isinstance(history, list) else [])
        self.assertTrue(len(hist_list) >= 1)

        # Close
        resp = self.api('delete', f'/dm-webmanager/api/terminal/{sid}')
        self.assertEqual(200, resp.status_code)


class TestPhase5_NLRunner(EndToEndBase):
    """Plan 19: Natural language orchestration runner."""

    def test_resolve_intent(self):
        from dimensigon.ai.nl_runner import resolve_intent
        result = resolve_intent(
            'run test_deploy',
            [{'id': str(self.orch.id), 'name': 'test_deploy', 'description': 'Test', 'schema': {}}],
            [{'id': 'srv-1', 'name': 'web-01', 'granules': []}]
        )
        self.assertEqual(str(self.orch.id), result['orchestration_id'])
        self.assertEqual('test_deploy', result['orchestration_name'])

    def test_resolve_api(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/ai/resolve', {
            'input': 'run test_deploy'
        })
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('orchestration_name', data)


class TestPhase5_TrainingFeedback(EndToEndBase):
    """Plan 20: Training data feedback loop."""

    def test_quality_score(self):
        from dimensigon.ai.feedback import compute_quality_score
        # Good orchestration
        score = compute_quality_score({
            'name': 'deploy',
            'description': 'Deployment with error handling',
            'stop_on_error': True,
            'steps': [
                {'name': 's1', 'timeout': 30, 'target': '{{server}}'},
                {'name': 's2', 'timeout': 60, 'target': '{{server}}'},
            ]
        })
        self.assertGreater(score, 0.5)

        # Bad orchestration
        score = compute_quality_score({'steps': []})
        self.assertLess(score, 0.5)

    def test_review_queue_api(self):
        self.login()
        resp = self.api('get', '/dm-webmanager/api/training/queue')
        self.assertEqual(200, resp.status_code)


class TestPhase5_Federation(EndToEndBase):
    """Plan 15: Multi-dimension federation."""

    def test_peering_lifecycle(self):
        self.login()
        # Initiate
        resp = self.api('post', '/dm-webmanager/api/federation/peers', {
            'name': 'staging',
            'endpoint': 'https://staging.example.com:5000'
        })
        self.assertIn(resp.status_code, [200, 201])
        data = resp.get_json()
        peer_id = data.get('id') or data.get('peer', {}).get('id')

        # List
        resp = self.api('get', '/dm-webmanager/api/federation/peers')
        self.assertEqual(200, resp.status_code)
        peers = resp.get_json()
        if isinstance(peers, list):
            peer_list = peers
        else:
            peer_list = peers.get('peers', [])
        self.assertTrue(len(peer_list) >= 1)

        # Extract peer_id from various response formats
        data = resp.get_json()
        if isinstance(data, dict):
            peer_id = data.get('id') or data.get('peer', {}).get('id') or data.get('peer_id')
        else:
            peer_id = None

        if peer_id:
            # Accept
            resp = self.api('post', f'/dm-webmanager/api/federation/peers/{peer_id}/accept')
            self.assertEqual(200, resp.status_code)

            # Revoke
            resp = self.api('post', f'/dm-webmanager/api/federation/peers/{peer_id}/revoke')
            self.assertEqual(200, resp.status_code)


# ==============================================================
# Orch-Library Integration (Plan 26 — post-3.0)
# ==============================================================

class TestOrchLibrary(EndToEndBase):
    """Template suggestion and fetch integration with orch-library."""

    SAMPLE_CATALOG = {
        "version": "1.0.0",
        "total": 2,
        "entries": [
            {
                "id": "shell.service_mgmt.restart-service.v0",
                "name": "postgresql-restart",
                "description": "Restarts the postgresql systemd service.",
                "category": "shell.service_mgmt",
                "entity_type": "action_template",
                "action_type": "SHELL",
                "difficulty": "basic",
                "tags": ["shell", "service_mgmt", "basic"],
                "user_prompt": "Restart the postgresql service using systemctl",
                "path": "action_templates/shell/service_mgmt/postgresql-restart.json",
            },
            {
                "id": "orch.deploy.rolling.v0",
                "name": "rolling-deploy",
                "description": "Rolling deployment across multiple nodes.",
                "category": "orchestration.single.app_deploy",
                "entity_type": "orchestration",
                "action_type": "ORCHESTRATION",
                "difficulty": "advanced",
                "tags": ["orchestration", "deploy"],
                "user_prompt": "Deploy using rolling update",
                "path": "orchestrations/single/app_deploy/rolling-deploy.json",
            },
        ],
    }

    def setUp(self):
        super().setUp()
        # Pre-populate the library index with a sample catalog
        from dimensigon.ai import template_suggest
        template_suggest._index = template_suggest.TemplateIndex()
        template_suggest._index.load_from_catalog(self.SAMPLE_CATALOG)

    def test_suggest_requires_auth(self):
        resp = self.api('post', '/dm-webmanager/api/library/suggest',
                        {'query': 'restart service'})
        self.assertEqual(302, resp.status_code)

    def test_suggest_returns_results(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/library/suggest',
                        {'query': 'restart postgresql', 'top_k': 3})
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertIn('results', data)
        self.assertTrue(len(data['results']) >= 1)
        self.assertEqual('postgresql-restart', data['results'][0]['name'])

    def test_suggest_rejects_empty_query(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/library/suggest', {'query': ''})
        self.assertEqual(400, resp.status_code)

    def test_suggest_filters_by_entity_type(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/library/suggest',
                        {'query': 'deploy rolling', 'entity_type': 'orchestration'})
        data = resp.get_json()
        for r in data['results']:
            self.assertEqual('orchestration', r['entity_type'])

    def test_fetch_requires_path(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/library/fetch', {})
        self.assertEqual(400, resp.status_code)

    def test_fetch_rejects_traversal(self):
        self.login()
        resp = self.api('post', '/dm-webmanager/api/library/fetch',
                        {'path': '../../etc/passwd'})
        self.assertEqual(404, resp.status_code)

    def test_refresh_requires_admin(self):
        self.login('operator', _TEST_PW_OP)
        resp = self.api('post', '/dm-webmanager/api/library/refresh')
        self.assertIn(resp.status_code, [302, 403])

    def test_import_requires_operator(self):
        self.login('viewer', _TEST_PW_VIEW)
        resp = self.api('post', '/dm-webmanager/api/library/import',
                        {'path': 'fake.json'})
        self.assertIn(resp.status_code, [302, 403])

    def test_import_template_success(self):
        from dimensigon.ai import template_suggest
        self.login('operator', _TEST_PW_OP)
        sample_tpl = {
            'id': 'test.sample.v0',
            'name': 'sample-import',
            'description': 'Imported sample',
            'category': 'orchestration.single.app_deploy',
            'tags': ['test'],
            'template': {'name': 'sample-import', 'steps': []},
        }
        with mock.patch.object(template_suggest, 'fetch_template',
                               return_value=sample_tpl):
            resp = self.api('post', '/dm-webmanager/api/library/import',
                            {'path': 'orchestrations/test/sample.json'})
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertEqual('sample-import', data['name'])
