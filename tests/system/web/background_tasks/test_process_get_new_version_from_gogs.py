import os
from unittest import mock
from unittest.mock import patch

import requests
import responses
from pkg_resources import parse_version
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.domain.entities import Dimension
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.web import create_app, db
from dimensigon.web.background_tasks import process_get_new_version_from_gogs, \
    upgrader_logger

gogs_content = """
<div class="ui container">
		<h2 class="ui header">
			Releases
		</h2>
		<ul id="release-list">
				<li class="ui grid">
					<div class="ui four wide column meta">
						<span class="commit">
							<a href="/dimensigon/dimensigon/src/d3aad4973fe692c4fcefede8eb53a1c9e32749b2" rel="nofollow"><i class="code icon"></i> d3aad4973f</a>
						</span>
					</div>
					<div class="ui twelve wide column detail">
							<h4>
								<a href="/dimensigon/dimensigon/src/v0.1.a1" rel="nofollow"><i class="tag icon"></i> v0.1.a1</a>
							</h4>
							<div class="download">
								<a href="/dimensigon/dimensigon/archive/v0.1.a1.zip" rel="nofollow"><i class="octicon octicon-file-zip"></i>ZIP</a>
								<a href="/dimensigon/dimensigon/archive/v0.1.a1.tar.gz"><i class="octicon octicon-file-zip"></i>TAR.GZ</a>
							</div>
						<span class="dot">&nbsp;</span>
					</div>
				</li>
				<li class="ui grid">
					<div class="ui four wide column meta">
						<span class="commit">
							<a href="/dimensigon/dimensigon/src/2184389034cec9620c44594ae6c174e676434db5" rel="nofollow"><i class="code icon"></i> 2184389034</a>
						</span>
					</div>
					<div class="ui twelve wide column detail">
							<h4>
								<a href="/dimensigon/dimensigon/src/v0.0.1" rel="nofollow"><i class="tag icon"></i> v0.0.1</a>
							</h4>
							<div class="download">
								<a href="/dimensigon/dimensigon/archive/v0.0.1.zip" rel="nofollow"><i class="octicon octicon-file-zip"></i>ZIP</a>
								<a href="/dimensigon/dimensigon/archive/v0.0.1.tar.gz"><i class="octicon octicon-file-zip"></i>TAR.GZ</a>
							</div>
						<span class="dot">&nbsp;</span>
					</div>
				</li>
		</ul>
		<div class="center">
			<a class="ui small button disabled">
				Página Anterior
			</a>
			<a class="ui small button disabled">
				Página Siguiente
			</a>
		</div>
	</div>
"""


class TestProcessGetNewVersionFromGogs(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        with self.app.app_context():
            db.create_all()
            set_initial()
            d = Dimension(name='test', current=True)
            db.session.add(d)
            db.session.commit()
        self.client = self.app.test_client(use_cookies=True)
        self.setUpPyfakefs()
        self.fs.create_dir(self.app.config['SOFTWARE_REPO'])

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('dimensigon.web.background_tasks.run_elevator')
    @responses.activate
    def test_internet_upgrade(self, mock_run_elevator):
        with mock.patch('dimensigon.web.background_tasks.dm_version', '0.0.1'):
            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/releases',
                          body=gogs_content)

            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                          body=b"v0.1.a1")

            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                          body=b"v0.0.1")

            process_get_new_version_from_gogs(self.app)

            self.assertTrue(os.path.exists(
                os.path.join(self.app.config['SOFTWARE_REPO'], 'dimensigon', 'dimensigon-v0.1.a1.tar.gz')))
            self.assertEqual(
                (os.path.join(self.app.config['SOFTWARE_REPO'], 'dimensigon', 'dimensigon-v0.1.a1.tar.gz'),
                 parse_version('v0.1.a1'),
                 upgrader_logger),
                mock_run_elevator.call_args[0])

    @patch('dimensigon.web.background_tasks.run_elevator')
    @responses.activate
    def test_internet_not_upgrade(self, mock_run_elevator):
        with mock.patch('dimensigon.web.background_tasks.dm_version', '0.1'):
            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/releases',
                          body=gogs_content)

            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                          body=b"v0.1.a1")

            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                          body=b"v0.0.1")

            process_get_new_version_from_gogs(self.app)

            self.assertFalse(mock_run_elevator.called)

    @patch('dimensigon.web.background_tasks.run_elevator')
    @responses.activate
    def test_no_internet_no_upgrade(self, mock_run_elevator):
        with mock.patch('dimensigon.web.background_tasks.dm_version', '0.1'):
            responses.add(method='GET',
                          url=self.app.config['GIT_REPO'] + '/dimensigon/dimensigon/releases',
                          body=requests.exceptions.ConnectionError('No connection'))

            process_get_new_version_from_gogs(self.app)

            self.assertFalse(mock_run_elevator.called)
