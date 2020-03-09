import os
from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

import aiohttp
import requests
import responses
from aioresponses import aioresponses

import dm
from dm.domain.entities import Server, Software, SoftwareServerAssociation, Transfer
from dm.domain.entities.bootstrap import set_initial
from dm.network.gateway import pack_msg
from dm.use_cases.background_tasks import check_new_versions, check_catalog
from dm.use_cases.interactor import Dimension, TransferStatus
from dm.web import create_app, db

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


class TestCheckNewVersions(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Server.set_initial()
        d = Dimension(name='test', current=True)
        db.session.add(d)
        db.session.commit()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.use_cases.background_tasks.lock_scope')
    @patch('dm.use_cases.background_tasks.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.background_tasks.md5')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_internet_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen, mock_lock):
        import dm.use_cases.interactor
        dm.use_cases.background_tasks.dm_version = '0.0.1'
        mock_lock.__enter__.return_value = None

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=gogs_content)

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                      body=b"v0.1.a1")

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                      body=b"v0.0.1")

        mock_md5.return_value = b"md5"
        mock_exists.return_value = False
        check_new_versions(self.app)

        self.assertEqual((['python', 'elevator.py', '-d',
                           os.path.join(self.app.config['SOFTWARE_DIR'], 'dimensigon-v0.1.a1.tar.gz')],),
                         mock_popen.call_args[0])

    @patch('dm.use_cases.background_tasks.lock_scope')
    @patch('dm.use_cases.background_tasks.subprocess.Popen')
    @patch('dm.use_cases.background_tasks.os.path.exists')
    @patch('dm.use_cases.background_tasks.md5')
    @patch('dm.use_cases.background_tasks.open')
    @responses.activate
    def test_internet_not_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen, mock_lock):
        import dm.use_cases.interactor
        dm.use_cases.background_tasks.dm_version = '0.1'
        mock_lock.__enter__.return_value = None

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=gogs_content)

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                      body=b"v0.1.a1")

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                      body=b"v0.0.1")

        mock_md5.return_value = b"md5"
        mock_exists.return_value = False
        check_new_versions(self.app)

        self.assertFalse(mock_popen.called)

    @patch('dm.use_cases.background_tasks.lock_scope')
    @patch('dm.use_cases.background_tasks.subprocess.Popen')
    @patch('dm.use_cases.background_tasks.os.path.exists')
    @patch('dm.use_cases.background_tasks.open')
    @responses.activate
    def test_no_internet_upgrade(self, mock_open, mock_exists, mock_popen, mock_lock):
        import dm.use_cases.interactor
        dm.use_cases.background_tasks.dm_version = '0.1'
        mock_lock.__enter__.return_value = None

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_exists.return_value = False

        soft = Software(name='dimensigon', version='v0.2',
                        filename='dimensigon-v0.2.tar.gz', size=10, checksum=b'10')
        ssa = SoftwareServerAssociation(software=soft, server=Server.get_current(),
                                        path=self.app.config['SOFTWARE_DIR'])
        db.session.add(soft)
        db.session.add(ssa)
        db.session.commit()

        check_new_versions()

        self.assertEqual((['python', 'elevator.py', '-d',
                           os.path.join(self.app.config['SOFTWARE_DIR'], 'dimensigon-v0.2.tar.gz')],),
                         mock_popen.call_args[0])

    @patch('dm.use_cases.background_tasks.lock_scope')
    @patch('dm.use_cases.background_tasks.subprocess.Popen')
    @patch('dm.use_cases.background_tasks.os.path.exists')
    @patch('dm.use_cases.background_tasks.md5')
    @patch('dm.use_cases.background_tasks.open')
    @responses.activate
    def test_no_internet_no_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen, mock_lock):
        import dm.use_cases.interactor
        dm.use_cases.background_tasks.dm_version = '0.1'
        mock_lock.__enter__.return_value = None

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_md5.return_value = b"md5"
        mock_exists.return_value = False
        check_new_versions()

        self.assertFalse(mock_popen.called)

    @patch('dm.use_cases.background_tasks.lock_scope')
    @patch('dm.use_cases.background_tasks.subprocess.Popen')
    @patch('dm.use_cases.background_tasks.os.path.exists')
    @patch('dm.use_cases.background_tasks.open')
    @responses.activate
    def test_no_internet_upgrade_remote_server(self, mock_open, mock_exists, mock_popen, mock_lock):
        import dm.use_cases.interactor
        dm.use_cases.background_tasks.dm_version = '0.1'
        mock_lock.__enter__.return_value = None

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_exists.return_value = False
        r_server = Server(name='RemoteServer', ip='8.8.8.8', port=5000, dns_name='remoteserver.local', cost=0)
        soft = Software(name='dimensigon', version='v0.2',
                        filename='dimensigon-v0.2.tar.gz', size=10, checksum=b'10')
        ssa = SoftwareServerAssociation(software=soft, server=r_server,
                                        path=self.app.config['SOFTWARE_DIR'])
        db.session.add(r_server)
        db.session.add(soft)
        db.session.add(ssa)
        db.session.commit()

        t = Transfer(software=soft, dest_path='', filename='', num_chunks=5, status=TransferStatus.COMPLETED)
        db.session.add(t)
        db.session.commit()

        responses.add(method='POST',
                      # TODO: change static url for url_for
                      url=f"http://remoteserver.local:5000/api/v1.0/software/send",
                      # url=f"https://remoteserver.local:5000{url_for('api_1_0.software_send')}",
                      json=pack_msg(data={'transfer_id': t.id},
                                    priv_key=getattr(Dimension.get_current(), 'private'),
                                    pub_key=getattr(Dimension.get_current(), 'public'))
                      )

        check_new_versions(timeout_wait_transfer=0.1, refresh_interval=0.05)

        self.assertEqual((['python', 'elevator.py', '-d',
                           os.path.join(self.app.config['SOFTWARE_DIR'], 'dimensigon-v0.2.tar.gz')],),
                         mock_popen.call_args[0])


class TestCheckCatalog(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        set_initial()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.use_cases.interactor.lock_scope')
    @patch('dm.domain.entities.get_now')
    @patch('dm.use_cases.background_tasks.upgrade_catalog_from_server')
    @aioresponses()
    def test_check_catalog(self, mock_upgrade, mock_now, mock_lock, m):
        mock_lock.__enter__.return_value = None
        mock_now.return_value = datetime(2019, 4, 1)
        s1 = Server('node1', cost=0)
        s2 = Server('node2', cost=0)
        db.session.add_all([s1, s2])
        db.session.commit()

        m.get(url=s1.url('root.healthcheck'),
              payload=dict(version=dm.__version__, catalog_version='20190401000000000000'))
        m.get(url=s2.url('root.healthcheck'),
              payload=dict(version=dm.__version__, catalog_version='20190401000000000001'))

        check_catalog(self.app)

        mock_upgrade.assert_called_once_with(s2)

    @patch('dm.use_cases.interactor.lock_scope')
    @patch('dm.domain.entities.get_now')
    @patch('dm.use_cases.background_tasks.upgrade_catalog_from_server')
    @aioresponses()
    def test_check_catalog_no_upgrade(self, mock_upgrade, mock_now, mock_lock, m):
        mock_lock.__enter__.return_value = None
        mock_now.return_value = datetime(2019, 4, 1)
        s1 = Server('node1', cost=0)
        s2 = Server('node2', cost=0)
        db.session.add_all([s1, s2])
        db.session.commit()

        m.get(url=s1.url('root.healthcheck'),
              payload=dict(version=dm.__version__, catalog_version='20190401000000000000'))
        m.get(url=s2.url('root.healthcheck'),
              payload=dict(version=dm.__version__, catalog_version='20190401000000000000'))

        check_catalog(self.app)

        self.assertEqual(0, mock_upgrade.call_count)

        m.get(url=s1.url('root.healthcheck'), exception=aiohttp.ClientError())
        m.get(url=s2.url('root.healthcheck'), exception=aiohttp.ClientError())

        check_catalog(self.app)

        self.assertEqual(0, mock_upgrade.call_count)
