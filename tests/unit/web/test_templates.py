"""Tests for orchestration templates / marketplace feature."""
import json
from unittest import TestCase

from dimensigon.domain.entities import User
from dimensigon.domain.entities.template import OrchTemplate
from dimensigon.web import create_app, db


class TestTemplateCRUD(TestCase):
    """Tests for template API endpoints."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create test user
        self.user = User(
            id='00000000-0000-0000-0000-000000000099',
            name='testadmin', groups=['administrator'], active=True
        )
        self.user.set_password('pass')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        return self.client.post(
            '/dm-webmanager/login',
            data=json.dumps({'username': 'testadmin', 'password': 'pass'}),
            content_type='application/json'
        )

    def _create_template(self, **overrides):
        payload = {
            'name': 'Deploy Nginx',
            'description': 'Deploy Nginx to target servers',
            'category': 'deployment',
            'tags': ['nginx', 'web', 'deploy'],
            'json_content': {
                'name': 'Deploy Nginx',
                'steps': [
                    {'action_template_id': 'at-1', 'action_name': 'Install Nginx', 'target': ['web1']},
                    {'action_template_id': 'at-2', 'action_name': 'Start Nginx', 'target': ['web1'], 'parents': ['step-1']},
                ],
            },
        }
        payload.update(overrides)
        return self.client.post(
            '/dm-webmanager/api/templates',
            data=json.dumps(payload),
            content_type='application/json'
        )

    # --- List ---

    def test_list_templates_empty(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/templates')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(data['templates'], [])
        self.assertEqual(data['total'], 0)

    def test_list_templates_returns_items(self):
        self._login()
        self._create_template()
        resp = self.client.get('/dm-webmanager/api/templates')
        data = resp.get_json()
        self.assertEqual(1, len(data['templates']))
        self.assertEqual('Deploy Nginx', data['templates'][0]['name'])

    def test_list_templates_search_by_name(self):
        self._login()
        self._create_template(name='Deploy Nginx', description='Web server setup', tags=['web'])
        self._create_template(name='Monitor Redis', description='Cache monitoring', tags=['cache'])
        resp = self.client.get('/dm-webmanager/api/templates?search=Nginx')
        data = resp.get_json()
        self.assertEqual(1, len(data['templates']))
        self.assertEqual('Deploy Nginx', data['templates'][0]['name'])

    def test_list_templates_search_by_description(self):
        self._login()
        self._create_template(name='Template A', description='Setup PostgreSQL database')
        self._create_template(name='Template B', description='Deploy web app')
        resp = self.client.get('/dm-webmanager/api/templates?search=PostgreSQL')
        data = resp.get_json()
        self.assertEqual(1, len(data['templates']))
        self.assertEqual('Template A', data['templates'][0]['name'])

    def test_list_templates_filter_by_category(self):
        self._login()
        self._create_template(name='Deploy App', category='deployment')
        self._create_template(name='Monitor App', category='monitoring')
        resp = self.client.get('/dm-webmanager/api/templates?category=monitoring')
        data = resp.get_json()
        self.assertEqual(1, len(data['templates']))
        self.assertEqual('Monitor App', data['templates'][0]['name'])

    def test_list_templates_pagination(self):
        self._login()
        for i in range(5):
            self._create_template(name=f'Template {i}')
        resp = self.client.get('/dm-webmanager/api/templates?page=1&per_page=2')
        data = resp.get_json()
        self.assertEqual(2, len(data['templates']))
        self.assertEqual(5, data['total'])
        self.assertEqual(1, data['page'])
        self.assertEqual(2, data['per_page'])

    # --- Create ---

    def test_create_template_success(self):
        self._login()
        resp = self._create_template()
        self.assertEqual(201, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Deploy Nginx', data['name'])
        self.assertEqual('deployment', data['category'])
        self.assertIn('nginx', data['tags'])
        self.assertIsNotNone(data['json_content'])
        self.assertIsNotNone(data['id'])

    def test_create_template_missing_name(self):
        self._login()
        resp = self._create_template(name='')
        self.assertEqual(400, resp.status_code)
        self.assertIn('name is required', resp.get_json()['error'])

    def test_create_template_invalid_category(self):
        self._login()
        resp = self._create_template(category='invalid_cat')
        self.assertEqual(400, resp.status_code)
        self.assertIn('Invalid category', resp.get_json()['error'])

    def test_create_template_missing_json_content(self):
        self._login()
        resp = self._create_template(json_content=None)
        self.assertEqual(400, resp.status_code)
        self.assertIn('json_content is required', resp.get_json()['error'])

    # --- Get single ---

    def test_get_template(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        resp = self.client.get(f'/dm-webmanager/api/templates/{template_id}')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual('Deploy Nginx', data['name'])
        self.assertIn('json_content', data)
        self.assertIsNotNone(data['json_content'])

    def test_get_template_not_found(self):
        self._login()
        resp = self.client.get('/dm-webmanager/api/templates/00000000-0000-0000-0000-999999999999')
        self.assertEqual(404, resp.status_code)

    # --- Rate ---

    def test_rate_template_upvote(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        resp = self.client.post(
            f'/dm-webmanager/api/templates/{template_id}/rate',
            data=json.dumps({'rating': 1}),
            content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(1, data['rating_sum'])
        self.assertEqual(1, data['rating_count'])
        self.assertEqual(1.0, data['rating'])

    def test_rate_template_downvote(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        resp = self.client.post(
            f'/dm-webmanager/api/templates/{template_id}/rate',
            data=json.dumps({'rating': -1}),
            content_type='application/json'
        )
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(-1, data['rating_sum'])
        self.assertEqual(1, data['rating_count'])

    def test_rate_template_invalid_value(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        resp = self.client.post(
            f'/dm-webmanager/api/templates/{template_id}/rate',
            data=json.dumps({'rating': 5}),
            content_type='application/json'
        )
        self.assertEqual(400, resp.status_code)
        self.assertIn('rating must be 1 or -1', resp.get_json()['error'])

    def test_rate_template_multiple_votes(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        # Three upvotes, one downvote
        for _ in range(3):
            self.client.post(
                f'/dm-webmanager/api/templates/{template_id}/rate',
                data=json.dumps({'rating': 1}),
                content_type='application/json'
            )
        self.client.post(
            f'/dm-webmanager/api/templates/{template_id}/rate',
            data=json.dumps({'rating': -1}),
            content_type='application/json'
        )

        resp = self.client.get(f'/dm-webmanager/api/templates/{template_id}')
        data = resp.get_json()
        self.assertEqual(2, data['rating_sum'])
        self.assertEqual(4, data['rating_count'])
        self.assertEqual(0.5, data['rating'])

    def test_rate_template_not_found(self):
        self._login()
        resp = self.client.post(
            '/dm-webmanager/api/templates/00000000-0000-0000-0000-999999999999/rate',
            data=json.dumps({'rating': 1}),
            content_type='application/json'
        )
        self.assertEqual(404, resp.status_code)

    # --- Use ---

    def test_use_template_returns_json_content(self):
        self._login()
        create_resp = self._create_template()
        template_id = create_resp.get_json()['id']

        resp = self.client.post(f'/dm-webmanager/api/templates/{template_id}/use')
        self.assertEqual(200, resp.status_code)
        data = resp.get_json()
        self.assertEqual(template_id, data['template_id'])
        self.assertEqual('Deploy Nginx', data['name'])
        self.assertIn('json_content', data)
        self.assertIsNotNone(data['json_content'])
        self.assertEqual('Deploy Nginx', data['json_content']['name'])
        self.assertEqual(2, len(data['json_content']['steps']))

    def test_use_template_not_found(self):
        self._login()
        resp = self.client.post('/dm-webmanager/api/templates/00000000-0000-0000-0000-999999999999/use')
        self.assertEqual(404, resp.status_code)

    # --- Auth required ---

    def test_templates_require_auth(self):
        for url in ['/dm-webmanager/api/templates']:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, (401, 302, 422),
                          f'{url} should require auth, got {resp.status_code}')


class TestOrchTemplateModel(TestCase):
    """Tests for the OrchTemplate model itself."""

    def setUp(self):
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'testnode'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_rating_property_zero_when_no_votes(self):
        tpl = OrchTemplate(name='Test', category='custom')
        self.assertEqual(0, tpl.rating)

    def test_rating_property_computes_average(self):
        tpl = OrchTemplate(name='Test', category='custom', rating_sum=7, rating_count=4)
        self.assertEqual(1.75, tpl.rating)

    def test_to_json_excludes_content_by_default(self):
        tpl = OrchTemplate(name='Test', category='deployment', json_content={'steps': []})
        db.session.add(tpl)
        db.session.commit()
        data = tpl.to_json(include_content=False)
        self.assertNotIn('json_content', data)
        self.assertEqual('Test', data['name'])

    def test_to_json_includes_content_when_requested(self):
        tpl = OrchTemplate(name='Test', category='deployment', json_content={'steps': []})
        db.session.add(tpl)
        db.session.commit()
        data = tpl.to_json(include_content=True)
        self.assertIn('json_content', data)
        self.assertEqual({'steps': []}, data['json_content'])
