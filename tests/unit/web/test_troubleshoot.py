"""Tests for AI-powered troubleshooting module and API endpoints."""
import json
from unittest import TestCase

from dimensigon.ai.troubleshoot import analyze_failure, TROUBLESHOOT_PROMPT
from dimensigon.domain.entities import User, Orchestration, Step, ActionTemplate, ActionType
from dimensigon.web import create_app, db


class TestAnalyzeFailure(TestCase):
    """Unit tests for the rule-based analyze_failure function."""

    def test_permission_denied(self):
        result = analyze_failure({
            'command': 'cat /etc/shadow',
            'stdout': '',
            'stderr': 'cat: /etc/shadow: Permission denied',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('permission', result['root_cause'].lower())
        self.assertIn('sudo', result['suggestion'].lower())
        self.assertEqual(result['modified_command'], 'sudo cat /etc/shadow')

    def test_permission_denied_already_sudo(self):
        result = analyze_failure({
            'command': 'sudo cat /etc/shadow',
            'stdout': '',
            'stderr': 'Permission denied',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        # Should not double-prefix sudo
        self.assertIsNone(result['modified_command'])

    def test_command_not_found(self):
        result = analyze_failure({
            'command': 'foobar --version',
            'stdout': '',
            'stderr': 'bash: foobar: command not found',
            'rc': 127,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('not installed', result['root_cause'].lower())
        self.assertIsNone(result['modified_command'])

    def test_no_such_file(self):
        result = analyze_failure({
            'command': 'cat /nonexistent/file.txt',
            'stdout': '',
            'stderr': 'cat: /nonexistent/file.txt: No such file or directory',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('file or directory', result['root_cause'].lower())

    def test_connection_refused(self):
        result = analyze_failure({
            'command': 'curl http://localhost:9999',
            'stdout': '',
            'stderr': 'curl: (7) Failed to connect to localhost port 9999: Connection refused',
            'rc': 7,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('connection', result['root_cause'].lower())
        self.assertIn('service', result['suggestion'].lower())

    def test_timeout(self):
        result = analyze_failure({
            'command': 'curl --connect-timeout 5 http://slow-host:8080',
            'stdout': '',
            'stderr': 'curl: (28) Connection timed out after 5001 milliseconds',
            'rc': 28,
        })
        self.assertIn(result['confidence'], ('high', 'medium'))
        self.assertIn('timed out', result['root_cause'].lower())

    def test_disk_full(self):
        result = analyze_failure({
            'command': 'dd if=/dev/zero of=/tmp/bigfile bs=1M count=10000',
            'stdout': '',
            'stderr': 'dd: error writing /tmp/bigfile: No space left on device',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('disk space', result['root_cause'].lower())

    def test_dns_failure(self):
        result = analyze_failure({
            'command': 'curl http://nonexistent.invalid',
            'stdout': '',
            'stderr': 'Could not resolve host: nonexistent.invalid',
            'rc': 6,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('dns', result['root_cause'].lower())

    def test_auth_failure(self):
        result = analyze_failure({
            'command': 'mysql -u root -p',
            'stdout': '',
            'stderr': 'ERROR 1045 (28000): Access denied for user',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('authentication', result['root_cause'].lower())

    def test_syntax_error(self):
        result = analyze_failure({
            'command': 'bash -c "if ["',
            'stdout': '',
            'stderr': 'bash: syntax error near unexpected token',
            'rc': 2,
        })
        self.assertIn(result['confidence'], ('high', 'medium'))
        self.assertIn('syntax', result['root_cause'].lower())

    def test_oom_killed(self):
        result = analyze_failure({
            'command': 'java -jar bigapp.jar',
            'stdout': '',
            'stderr': 'Killed',
            'rc': 137,
        })
        self.assertIn(result['confidence'], ('high', 'medium'))
        self.assertIn('killed', result['root_cause'].lower())

    def test_unknown_error_fallback(self):
        result = analyze_failure({
            'command': 'mystery-cmd',
            'stdout': 'some generic output',
            'stderr': 'something went wrong',
            'rc': 42,
        })
        self.assertEqual(result['confidence'], 'low')
        self.assertIn('42', result['root_cause'])
        self.assertIsNone(result['modified_command'])

    def test_rc_zero_but_failed(self):
        result = analyze_failure({
            'command': 'check-health',
            'stdout': 'status: degraded',
            'stderr': '',
            'rc': 0,
        })
        self.assertEqual(result['confidence'], 'medium')
        self.assertIn('exit code 0', result['root_cause'].lower())

    def test_empty_input(self):
        result = analyze_failure({})
        self.assertIn('confidence', result)
        self.assertIn('root_cause', result)
        self.assertIn('suggestion', result)
        self.assertIn('modified_command', result)

    def test_pattern_in_stdout(self):
        """Patterns should be detected in stdout as well as stderr."""
        result = analyze_failure({
            'command': 'deploy.sh',
            'stdout': 'Error: Permission denied when writing to /opt/app',
            'stderr': '',
            'rc': 1,
        })
        self.assertEqual(result['confidence'], 'high')
        self.assertIn('permission', result['root_cause'].lower())

    def test_troubleshoot_prompt_exists(self):
        """TROUBLESHOOT_PROMPT template should contain expected placeholders."""
        self.assertIn('{command}', TROUBLESHOOT_PROMPT)
        self.assertIn('{stdout}', TROUBLESHOOT_PROMPT)
        self.assertIn('{stderr}', TROUBLESHOOT_PROMPT)
        self.assertIn('{rc}', TROUBLESHOOT_PROMPT)
        self.assertIn('{orchestration_name}', TROUBLESHOOT_PROMPT)
        self.assertIn('{step_name}', TROUBLESHOOT_PROMPT)
        self.assertIn('{server_name}', TROUBLESHOOT_PROMPT)


class TestTroubleshootAPI(TestCase):
    """Integration tests for the troubleshoot API endpoints."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create operator user
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testop', groups=['operator'], active=True,
        )
        self.user.set_password('pass')
        db.session.add(self.user)

        # Create orchestration + step for apply-fix testing
        self.orch = Orchestration(name='test-orch', version=1)
        db.session.add(self.orch)
        db.session.flush()

        at = ActionTemplate(
            name='shell', version=1, action_type=ActionType.SHELL,
            code='echo hello',
        )
        db.session.add(at)
        db.session.flush()

        self.step = Step(
            orchestration=self.orch, undo=False, action_template=at,
            code='echo old-command',
        )
        db.session.add(self.step)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testop', 'password': 'pass'}),
            content_type='application/json',
        )

    def test_troubleshoot_ad_hoc(self):
        """POST /api/ai/troubleshoot with ad-hoc data returns analysis."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/troubleshoot',
            data=json.dumps({
                'command': 'apt install foo',
                'stdout': '',
                'stderr': 'bash: apt: command not found',
                'rc': 127,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('root_cause', data)
        self.assertIn('suggestion', data)
        self.assertIn('confidence', data)
        self.assertIn('modified_command', data)
        self.assertEqual(data['confidence'], 'high')

    def test_troubleshoot_permission_denied(self):
        """Troubleshoot endpoint correctly identifies permission denied."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/troubleshoot',
            data=json.dumps({
                'command': 'cat /etc/shadow',
                'stdout': '',
                'stderr': 'Permission denied',
                'rc': 1,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('permission', data['root_cause'].lower())
        self.assertEqual(data['modified_command'], 'sudo cat /etc/shadow')

    def test_troubleshoot_requires_auth(self):
        """Troubleshoot endpoint requires authentication."""
        resp = self.client.post(
            '/dm-webmanager/api/ai/troubleshoot',
            data=json.dumps({'command': 'test', 'stderr': 'fail', 'rc': 1}),
            content_type='application/json',
        )
        # Should redirect or return 401/302
        self.assertIn(resp.status_code, (302, 401, 422))

    def test_apply_fix_success(self):
        """POST /api/ai/apply-fix updates step code."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': str(self.step.id),
                'orchestration_id': str(self.orch.id),
                'new_command': 'echo new-command',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['new_command'], 'echo new-command')
        self.assertEqual(data['old_command'], 'echo old-command')

        # Verify step was updated in DB
        db.session.refresh(self.step)
        self.assertEqual(self.step.code, 'echo new-command')

    def test_apply_fix_missing_step_id(self):
        """apply-fix returns 400 if step_id is missing."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'orchestration_id': str(self.orch.id),
                'new_command': 'echo fixed',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_apply_fix_missing_orchestration_id(self):
        """apply-fix returns 400 if orchestration_id is missing."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': str(self.step.id),
                'new_command': 'echo fixed',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_apply_fix_missing_new_command(self):
        """apply-fix returns 400 if new_command is missing."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': str(self.step.id),
                'orchestration_id': str(self.orch.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_apply_fix_orchestration_not_found(self):
        """apply-fix returns 404 for non-existent orchestration."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': str(self.step.id),
                'orchestration_id': '00000000-0000-0000-0000-000000000000',
                'new_command': 'echo fixed',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_apply_fix_step_not_found(self):
        """apply-fix returns 404 for non-existent step."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': '00000000-0000-0000-0000-000000000000',
                'orchestration_id': str(self.orch.id),
                'new_command': 'echo fixed',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_apply_fix_step_wrong_orchestration(self):
        """apply-fix returns 400 if step does not belong to the orchestration."""
        self._login()
        # Create a different orchestration
        other_orch = Orchestration(name='other-orch', version=1)
        db.session.add(other_orch)
        db.session.commit()

        resp = self.client.post(
            '/dm-webmanager/api/ai/apply-fix',
            data=json.dumps({
                'step_id': str(self.step.id),
                'orchestration_id': str(other_orch.id),
                'new_command': 'echo fixed',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_troubleshoot_missing_step_execution(self):
        """Troubleshoot with non-existent step_execution_id returns 404."""
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/ai/troubleshoot',
            data=json.dumps({
                'step_execution_id': '00000000-0000-0000-0000-000000000000',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)
