"""Tests for the orch-library template suggestion engine."""
import json
import sys
from unittest import TestCase, mock

# Pre-mock netifaces to avoid import-time failure in CI
if 'netifaces' not in sys.modules:
    mock_netifaces = mock.MagicMock()
    mock_netifaces.interfaces.return_value = ['lo']
    mock_netifaces.ifaddresses.return_value = {2: [{'addr': '127.0.0.1'}]}
    mock_netifaces.AF_INET = 2
    sys.modules['netifaces'] = mock_netifaces

from dimensigon.ai import template_suggest


SAMPLE_CATALOG = {
    "version": "1.0.0",
    "total": 4,
    "entries": [
        {
            "id": "shell.service_mgmt.restart-service.v0",
            "name": "postgresql-restart",
            "description": "Restarts the postgresql systemd service and verifies it becomes active.",
            "category": "shell.service_mgmt",
            "entity_type": "action_template",
            "action_type": "SHELL",
            "difficulty": "basic",
            "tags": ["shell", "service_mgmt", "basic"],
            "user_prompt": "Restart the postgresql service using systemctl",
            "path": "action_templates/shell/service_mgmt/postgresql-restart.json",
        },
        {
            "id": "shell.service_mgmt.restart-service.v1",
            "name": "nginx-restart",
            "description": "Restarts the nginx web server and confirms it's running.",
            "category": "shell.service_mgmt",
            "entity_type": "action_template",
            "action_type": "SHELL",
            "difficulty": "basic",
            "tags": ["shell", "service_mgmt", "basic", "nginx"],
            "user_prompt": "Restart the nginx web server",
            "path": "action_templates/shell/service_mgmt/nginx-restart.json",
        },
        {
            "id": "orch.deploy.rolling.v0",
            "name": "rolling-deploy",
            "description": "Rolling deployment across multiple nodes with health checks.",
            "category": "orchestration.single.app_deploy",
            "entity_type": "orchestration",
            "action_type": "ORCHESTRATION",
            "difficulty": "advanced",
            "tags": ["orchestration", "deploy", "rolling"],
            "user_prompt": "Deploy application using rolling update strategy",
            "path": "orchestrations/single/app_deploy/rolling-deploy.json",
        },
        {
            "id": "python.http_api.healthcheck.v0",
            "name": "http-healthcheck",
            "description": "Python HTTP health check with retries and custom timeouts.",
            "category": "python.http_api",
            "entity_type": "action_template",
            "action_type": "PYTHON",
            "difficulty": "intermediate",
            "tags": ["python", "http", "health"],
            "user_prompt": "Check if an HTTP service is healthy",
            "path": "action_templates/python/http_api/http-healthcheck.json",
        },
    ],
}


class TestTemplateIndex(TestCase):

    def setUp(self):
        self.idx = template_suggest.TemplateIndex()
        self.idx.load_from_catalog(SAMPLE_CATALOG)

    def test_index_size(self):
        self.assertEqual(4, self.idx.size)

    def test_search_exact_service_match(self):
        results = self.idx.search("restart postgresql service", top_k=3)
        self.assertTrue(len(results) >= 1)
        self.assertEqual("postgresql-restart", results[0]["name"])

    def test_search_nginx_match(self):
        results = self.idx.search("restart nginx web server", top_k=3)
        self.assertEqual("nginx-restart", results[0]["name"])

    def test_search_filters_by_entity_type(self):
        results = self.idx.search("deploy rolling", entity_type="orchestration")
        self.assertTrue(all(r["entity_type"] == "orchestration" for r in results))

    def test_search_filters_by_action_type(self):
        results = self.idx.search("health check", action_type="PYTHON")
        self.assertTrue(all(r["action_type"] == "PYTHON" for r in results))

    def test_search_filters_by_difficulty(self):
        results = self.idx.search("restart", difficulty="basic")
        self.assertTrue(all(r["difficulty"] == "basic" for r in results))

    def test_search_empty_query(self):
        self.assertEqual([], self.idx.search(""))

    def test_search_no_match(self):
        # Use a word that appears nowhere in the sample catalog
        results = self.idx.search("quantumfluxcapacitor")
        self.assertEqual(0, len(results))

    def test_score_present(self):
        results = self.idx.search("restart postgresql")
        self.assertIn("score", results[0])
        self.assertGreater(results[0]["score"], 0)

    def test_results_sorted_by_score_desc(self):
        results = self.idx.search("restart service")
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(results[i]["score"], results[i + 1]["score"])


class TestSuggestAPI(TestCase):

    def setUp(self):
        # Pre-populate the global index
        template_suggest._index = template_suggest.TemplateIndex()
        template_suggest._index.load_from_catalog(SAMPLE_CATALOG)

    def test_suggest_returns_results(self):
        result = template_suggest.suggest("restart postgres", top_k=3)
        self.assertIn("results", result)
        self.assertTrue(len(result["results"]) >= 1)
        self.assertEqual("postgresql-restart", result["results"][0]["name"])

    def test_suggest_respects_top_k(self):
        result = template_suggest.suggest("restart", top_k=1)
        self.assertLessEqual(len(result["results"]), 1)

    def test_suggest_includes_metadata(self):
        result = template_suggest.suggest("nginx")
        self.assertIn("query", result)
        self.assertIn("size", result)


class TestRefreshIndex(TestCase):

    def setUp(self):
        template_suggest._index = template_suggest.TemplateIndex()

    def test_refresh_fetches_from_url(self):
        with mock.patch('dimensigon.ai.template_suggest.requests.get') as mock_get:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = SAMPLE_CATALOG
            mock_resp.raise_for_status = mock.MagicMock()
            mock_get.return_value = mock_resp

            result = template_suggest.refresh_index(force=True)
            self.assertTrue(result["ok"])
            self.assertEqual(4, result["size"])
            self.assertFalse(result["cached"])

    def test_refresh_handles_fetch_failure(self):
        with mock.patch('dimensigon.ai.template_suggest.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network down")
            result = template_suggest.refresh_index(force=True)
            self.assertFalse(result["ok"])
            self.assertIn("error", result)

    def test_refresh_uses_cache_when_fresh(self):
        template_suggest._index.load_from_catalog(SAMPLE_CATALOG)
        result = template_suggest.refresh_index(force=False)
        self.assertTrue(result["ok"])
        self.assertTrue(result["cached"])


class TestFetchTemplate(TestCase):

    def test_fetch_template_success(self):
        with mock.patch('dimensigon.ai.template_suggest.requests.get') as mock_get:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {"id": "t1", "name": "test", "template": {}}
            mock_resp.raise_for_status = mock.MagicMock()
            mock_get.return_value = mock_resp

            result = template_suggest.fetch_template("action_templates/shell/foo/bar.json")
            self.assertIsNotNone(result)
            self.assertEqual("t1", result["id"])

    def test_fetch_template_rejects_absolute_path(self):
        self.assertIsNone(template_suggest.fetch_template("/etc/passwd"))

    def test_fetch_template_rejects_parent_traversal(self):
        self.assertIsNone(template_suggest.fetch_template("../../secret.json"))

    def test_fetch_template_handles_network_error(self):
        with mock.patch('dimensigon.ai.template_suggest.requests.get') as mock_get:
            mock_get.side_effect = Exception("Timeout")
            self.assertIsNone(template_suggest.fetch_template("valid/path.json"))
