import os
from unittest import TestCase
from unittest.mock import patch

import requests
import responses

from dm.domain.entities import Server, Software, SoftwareServerAssociation, Transfer
from dm.network.gateway import pack_msg
from dm.use_cases.interactor import check_new_versions, SoftwareFamily, Dimension, TransferStatus
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

    @patch('dm.use_cases.interactor.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.interactor.md5')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_internet_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen):
        import dm.use_cases.interactor
        dm.use_cases.interactor.dm_version = '0.0.1'

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
        check_new_versions()

        self.assertEqual((['python', 'elevator.py', '-d',
                           os.path.join(self.app.config['SOFTWARE_DIR'], 'dimensigon-v0.1.a1.tar.gz')],),
                         mock_popen.call_args[0])

    @patch('dm.use_cases.interactor.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.interactor.md5')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_internet_not_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen):
        import dm.use_cases.interactor
        dm.use_cases.interactor.dm_version = '0.1'

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
        check_new_versions()

        self.assertFalse(mock_popen.called)

    @patch('dm.use_cases.interactor.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_no_internet_upgrade(self, mock_open, mock_exists, mock_popen):
        import dm.use_cases.interactor
        dm.use_cases.interactor.dm_version = '0.1'

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_exists.return_value = False

        soft = Software(name='dimensigon', version='v0.2', family=SoftwareFamily.MIDDLEWARE,
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

    @patch('dm.use_cases.interactor.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.interactor.md5')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_no_internet_no_upgrade(self, mock_open, mock_md5, mock_exists, mock_popen):
        import dm.use_cases.interactor
        dm.use_cases.interactor.dm_version = '0.1'

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_md5.return_value = b"md5"
        mock_exists.return_value = False
        check_new_versions()

        self.assertFalse(mock_popen.called)

    @patch('dm.use_cases.interactor.subprocess.Popen')
    @patch('dm.use_cases.interactor.os.path.exists')
    @patch('dm.use_cases.interactor.open')
    @responses.activate
    def test_no_internet_upgrade_remote_server(self, mock_open, mock_exists, mock_popen):
        import dm.use_cases.interactor
        dm.use_cases.interactor.dm_version = '0.1'

        responses.add(method='GET',
                      url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                      body=requests.exceptions.ConnectionError('No connection'))

        mock_exists.return_value = False
        r_server = Server(name='RemoteServer', ip='8.8.8.8', port=5000, dns_name='remoteserver.local', cost=0)
        soft = Software(name='dimensigon', version='v0.2', family=SoftwareFamily.MIDDLEWARE,
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
