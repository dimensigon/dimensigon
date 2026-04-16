"""Tests for the Natural Language Orchestration Runner."""
from unittest import TestCase

from dimensigon.ai.nl_runner import resolve_intent, _extract_params, _extract_targets, NL_RUNNER_PROMPT


# Sample data used across tests
SAMPLE_ORCHESTRATIONS = [
    {'name': 'health-check', 'id': 'orch-1', 'description': 'Run health checks on servers', 'schema': {}},
    {'name': 'deploy-app', 'id': 'orch-2', 'description': 'Deploy application to target servers', 'schema': {}},
    {'name': 'restart-service', 'id': 'orch-3', 'description': 'Restart a service on target', 'schema': {}},
    {'name': 'backup-database', 'id': 'orch-4', 'description': 'Perform database backup', 'schema': {}},
    {'name': 'health-check-extended', 'id': 'orch-5', 'description': 'Extended health check with deep diagnostics', 'schema': {}},
]

SAMPLE_SERVERS = [
    {'name': 'web-server-01', 'id': 'srv-1', 'granules': ['web', 'frontend']},
    {'name': 'web-server-02', 'id': 'srv-2', 'granules': ['web', 'frontend']},
    {'name': 'db-server-01', 'id': 'srv-3', 'granules': ['database', 'backend']},
    {'name': 'app-server-01', 'id': 'srv-4', 'granules': ['app', 'backend']},
    {'name': 'monitor-01', 'id': 'srv-5', 'granules': ['monitoring']},
]


class TestResolveIntentExactMatch(TestCase):
    """Test resolve_intent when the orchestration name appears exactly in the input."""

    def test_exact_name_match(self):
        result = resolve_intent(
            'Run health-check on web-server-01',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        self.assertEqual(result['orchestration_id'], 'orch-1')
        self.assertEqual(result['orchestration_name'], 'health-check')
        self.assertGreaterEqual(result['confidence'], 0.8)

    def test_exact_match_case_insensitive(self):
        result = resolve_intent(
            'Execute Deploy-App now',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        self.assertEqual(result['orchestration_id'], 'orch-2')
        self.assertEqual(result['orchestration_name'], 'deploy-app')
        self.assertGreaterEqual(result['confidence'], 0.8)


class TestResolveIntentFuzzyMatch(TestCase):
    """Test resolve_intent with fuzzy/partial matches."""

    def test_fuzzy_partial_name(self):
        result = resolve_intent(
            'run backup on db-server-01',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        # Should match 'backup-database' via fuzzy matching
        self.assertEqual(result['orchestration_id'], 'orch-4')
        self.assertEqual(result['orchestration_name'], 'backup-database')
        self.assertGreater(result['confidence'], 0.0)

    def test_fuzzy_description_match(self):
        result = resolve_intent(
            'deploy application to all web servers',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        self.assertEqual(result['orchestration_id'], 'orch-2')
        self.assertEqual(result['orchestration_name'], 'deploy-app')


class TestResolveIntentAmbiguous(TestCase):
    """Test resolve_intent when multiple orchestrations could match."""

    def test_ambiguous_returns_alternatives(self):
        # "health" matches both health-check and health-check-extended
        result = resolve_intent(
            'health check',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        self.assertIsNotNone(result['orchestration_id'])
        # The best match should be health-check (shorter, starts with input)
        self.assertEqual(result['orchestration_name'], 'health-check')
        # Should have at least one alternative
        self.assertGreater(len(result['alternatives']), 0)
        alt_names = [a['name'] for a in result['alternatives']]
        self.assertIn('health-check-extended', alt_names)

    def test_no_match_returns_none(self):
        result = resolve_intent(
            'completely unrelated request about weather',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        # If nothing matches at all, orchestration_id should be None
        # or confidence should be low
        if result['orchestration_id'] is None:
            self.assertEqual(result['confidence'], 0.0)
        else:
            self.assertLess(result['confidence'], 0.7)


class TestParameterExtraction(TestCase):
    """Test parameter extraction from natural language input."""

    def test_key_value_pattern(self):
        params = _extract_params('run health-check timeout=30 env=production')
        self.assertEqual(params['timeout'], '30')
        self.assertEqual(params['env'], 'production')

    def test_with_pattern(self):
        params = _extract_params('deploy app with version 2.1.0')
        self.assertEqual(params['version'], '2.1.0')

    def test_using_pattern(self):
        params = _extract_params('restart service using port 8080')
        self.assertEqual(params['port'], '8080')

    def test_quoted_value(self):
        params = _extract_params('run task name="my long name"')
        self.assertEqual(params['name'], 'my long name')

    def test_no_params(self):
        params = _extract_params('just run health check')
        self.assertEqual(params, {})

    def test_mixed_patterns(self):
        params = _extract_params('deploy with branch main env=staging using port 3000')
        self.assertEqual(params['branch'], 'main')
        self.assertEqual(params['env'], 'staging')
        self.assertEqual(params['port'], '3000')


class TestTargetExtraction(TestCase):
    """Test target server extraction from natural language input."""

    def test_exact_server_name(self):
        targets = _extract_targets('run on web-server-01', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['name'], 'web-server-01')
        self.assertEqual(targets[0]['id'], 'srv-1')

    def test_all_servers(self):
        targets = _extract_targets('run on all servers', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 5)

    def test_all_granule_servers(self):
        targets = _extract_targets('deploy to all web servers', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 2)
        names = {t['name'] for t in targets}
        self.assertIn('web-server-01', names)
        self.assertIn('web-server-02', names)

    def test_granule_mention(self):
        targets = _extract_targets('check the database', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['name'], 'db-server-01')

    def test_multiple_server_names(self):
        targets = _extract_targets('run on web-server-01 and app-server-01', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 2)
        names = {t['name'] for t in targets}
        self.assertIn('web-server-01', names)
        self.assertIn('app-server-01', names)

    def test_no_targets(self):
        targets = _extract_targets('just run the task', SAMPLE_SERVERS)
        self.assertEqual(len(targets), 0)


class TestResolveIntentEndToEnd(TestCase):
    """End-to-end tests for resolve_intent combining all extraction."""

    def test_full_command(self):
        result = resolve_intent(
            'Run health-check on web-server-01 with timeout 60',
            SAMPLE_ORCHESTRATIONS,
            SAMPLE_SERVERS,
        )
        self.assertEqual(result['orchestration_name'], 'health-check')
        self.assertEqual(len(result['targets']), 1)
        self.assertEqual(result['targets'][0]['name'], 'web-server-01')
        self.assertEqual(result['params']['timeout'], '60')

    def test_empty_input(self):
        result = resolve_intent('', SAMPLE_ORCHESTRATIONS, SAMPLE_SERVERS)
        self.assertIsNone(result['orchestration_id'])
        self.assertEqual(result['confidence'], 0.0)
        self.assertEqual(result['targets'], [])
        self.assertEqual(result['params'], {})

    def test_prompt_template_exists(self):
        """Verify NL_RUNNER_PROMPT template string is defined."""
        self.assertIn('{user_input}', NL_RUNNER_PROMPT)
        self.assertIn('{orchestrations}', NL_RUNNER_PROMPT)
        self.assertIn('{servers}', NL_RUNNER_PROMPT)
