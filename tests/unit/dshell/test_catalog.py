import time
from unittest import TestCase, mock

from dimensigon.dshell.catalog import (
    CACHE_TTL,
    OrchestrationCatalog,
    fuzzy_match,
)


class TestFuzzyMatch(TestCase):
    """Tests for the fuzzy_match function -- no Flask context needed."""

    def test_empty_input_returns_all_sorted(self):
        candidates = ['cherry', 'banana', 'apple']
        result = fuzzy_match('', candidates)
        self.assertEqual(['apple', 'banana', 'cherry'], result)

    def test_exact_prefix_match(self):
        candidates = ['deploy', 'delete', 'debug']
        result = fuzzy_match('dep', candidates)
        self.assertEqual(['deploy'], result)

    def test_subsequence_match(self):
        candidates = ['deploy-app', 'restart-app', 'debug-panel']
        result = fuzzy_match('dpa', candidates)
        # 'deploy-app' matches (d..p..a) and 'debug-panel' matches (d..p..a)
        self.assertIn('deploy-app', result)
        self.assertIn('debug-panel', result)

    def test_no_match(self):
        candidates = ['alpha', 'bravo', 'charlie']
        result = fuzzy_match('xyz', candidates)
        self.assertEqual([], result)

    def test_case_insensitive(self):
        candidates = ['Deploy', 'DELETE', 'debug']
        result = fuzzy_match('DEL', candidates)
        self.assertIn('DELETE', result)

    def test_prefix_matches_sorted_first(self):
        candidates = ['x-deploy', 'deploy-x']
        result = fuzzy_match('dep', candidates)
        # 'deploy-x' starts with 'dep' so comes first
        self.assertEqual(result[0], 'deploy-x')

    def test_shorter_candidates_preferred(self):
        candidates = ['ab', 'a-longer-b', 'aXb']
        result = fuzzy_match('ab', candidates)
        # All match as subsequence; 'ab' is exact prefix match and shortest
        self.assertEqual(result[0], 'ab')

    def test_single_char_input(self):
        candidates = ['apple', 'banana', 'avocado']
        result = fuzzy_match('a', candidates)
        self.assertIn('apple', result)
        self.assertIn('avocado', result)
        self.assertIn('banana', result)

    def test_empty_candidates(self):
        result = fuzzy_match('test', [])
        self.assertEqual([], result)


class TestOrchestrationCatalogCacheExpiry(TestCase):
    """Tests for cache TTL behavior -- no DB required."""

    def test_cache_starts_expired(self):
        catalog = OrchestrationCatalog()
        self.assertTrue(catalog._is_expired)

    def test_cache_not_expired_after_refresh(self):
        catalog = OrchestrationCatalog()
        # Simulate a successful refresh by setting the timestamp directly
        catalog._last_refresh = time.time()
        self.assertFalse(catalog._is_expired)

    def test_cache_expires_after_ttl(self):
        catalog = OrchestrationCatalog()
        catalog._last_refresh = time.time() - CACHE_TTL - 1
        self.assertTrue(catalog._is_expired)

    def test_ensure_fresh_calls_refresh_when_expired(self):
        catalog = OrchestrationCatalog()
        catalog._last_refresh = 0.0
        with mock.patch.object(catalog, 'refresh') as mock_refresh:
            catalog._ensure_fresh()
            mock_refresh.assert_called_once()

    def test_ensure_fresh_skips_refresh_when_not_expired(self):
        catalog = OrchestrationCatalog()
        catalog._last_refresh = time.time()
        with mock.patch.object(catalog, 'refresh') as mock_refresh:
            catalog._ensure_fresh()
            mock_refresh.assert_not_called()


class TestOrchestrationCatalogGetters(TestCase):
    """Tests for getter methods using pre-populated cache data."""

    def _make_catalog(self):
        catalog = OrchestrationCatalog()
        catalog._orchestrations = {
            'deploy-app': {
                'description': 'Deploy the application',
                'version': 3,
                'schema': {
                    'required': ['input.version', 'input.env'],
                    'input': {'version': {'type': 'string'}, 'env': {'type': 'string'}},
                    'output': ['result'],
                },
                'target': ['frontend', 'backend'],
            },
            'restart-service': {
                'description': 'Restart a service',
                'version': 1,
                'schema': {
                    'required': ['input.service_name'],
                    'input': {'service_name': {'type': 'string'}},
                },
                'target': ['all'],
            },
        }
        catalog._server_names = ['web-01', 'web-02', 'db-01']
        # Mark cache as fresh
        catalog._last_refresh = time.time()
        return catalog

    def test_get_orchestration_names(self):
        catalog = self._make_catalog()
        names = catalog.get_orchestration_names()
        self.assertEqual(['deploy-app', 'restart-service'], names)

    def test_get_parameters_existing(self):
        catalog = self._make_catalog()
        params = catalog.get_parameters('deploy-app')
        self.assertIn('required', params)
        self.assertIn('input.version', params['required'])

    def test_get_parameters_missing(self):
        catalog = self._make_catalog()
        params = catalog.get_parameters('nonexistent')
        self.assertEqual({}, params)

    def test_get_target_names(self):
        catalog = self._make_catalog()
        targets = catalog.get_target_names('deploy-app')
        self.assertEqual(['frontend', 'backend'], targets)

    def test_get_target_names_missing(self):
        catalog = self._make_catalog()
        targets = catalog.get_target_names('nonexistent')
        self.assertEqual([], targets)

    def test_get_server_names(self):
        catalog = self._make_catalog()
        servers = catalog.get_server_names()
        self.assertEqual(['web-01', 'web-02', 'db-01'], servers)
