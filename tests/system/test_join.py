import re
from functools import partial
from unittest import TestCase
from unittest.mock import patch

import responses
import rsa
from flask import url_for
from flask.cli import cli
from flask_jwt_extended import create_access_token

from dm import db
from dm.domain.entities import Server, Dimension
from dm.web import create_app


class TestApi(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'server'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Server.set_initial()
        self.d_public, self.d_private = rsa.newkeys(2048)
        self.l_public, self.l_private = rsa.newkeys(1024)
        d = Dimension(name='test', current=True, public=self.d_public, private=self.d_private)
        db.session.add(d)
        db.session.commit()
        self.dimension = d.to_json()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.rsa.newkeys')
    def test_join_command(self, mock_rsa):
        resp = self.client.get(url_for('api_1_0.join_public', _external=False),
                               headers={'Authorization': "Bearer " + create_access_token('join')})

        mock_rsa.return_value = (self.l_public, self.l_private)

        def request_callback(request, client):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        with responses.RequestsMock() as rsps:
            rsps.add_callback(responses.POST,
                              re.compile('.*'),
                              callback=partial(request_callback, client=self.client))
            rsps.add_callback(responses.GET,
                              re.compile('.*'),
                              callback=partial(request_callback, client=self.client))

            from click.testing import CliRunner
            runner = CliRunner(echo_stdin=True)
            result = runner.invoke(cli, ['dm', 'join', '--no-ssl', 'server:5000', create_access_token('join')],
                                   catch_exceptions=False, env={''})

        self.assertEqual("Joining to dimension\nJoined to the dimension", result.stdout)
