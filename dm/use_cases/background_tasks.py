import logging
import os
import subprocess
import typing as t

import requests
from bs4 import BeautifulSoup
from flask import current_app
from pkg_resources import parse_version

from dm import db, __version__ as dm_version
from dm.domain.entities import Software, SoftwareServerAssociation, SoftwareFamily, Server, Dimension, Transfer, \
    TransferStatus
from dm.network.gateway import pack_msg, unpack_msg
from dm.use_cases import exceptions as ue
from dm.utils.helpers import get_filename_from_cd, md5

logger = logging.getLogger('backgroundTasks')

from dm.scheduler import scheduler


@scheduler.scheduled_job(id='interval', minutes=2)
def check_new_versions(timeout_wait_transfer=None, refresh_interval=None):
    """
    checks if new version in repo

    Parameters
    ----------
    timeout_wait_transfer:
        timeout waiting tranfer file to end.
    refresh_interval:
        time period to check if tranfer ended. Normally, used for test purposes

    Returns
    -------

    """
    logger.info('Starting Upgrade Process')
    base_url = os.environ.get('GIT_REPO') or 'https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
    releases_uri = '/dimensigon/dimensigon/releases'
    try:
        r = requests.get(base_url + releases_uri, verify=current_app.config['SSL_VERIFY'], timeout=10)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        r = None
        current_app.logger.info('Unable to contact to main repo')

    # get new versions from repo
    if r and r.status_code == 200:
        # get current software
        software_list: t.List = Software.query.filter_by(name='dimensigon').all()
        software_list.sort(key=lambda s: parse_version(s.version))
        gogs_versions = {}

        html_content = r.text
        soup = BeautifulSoup(html_content, 'html.parser')
        for li in soup.find(id='release-list').find_all('li'):
            version = li.h4.a.get_text(strip=True)
            uris = [a.attrs['href'] for a in li.find('div', class_='download').find_all('a') if
                    a.attrs['href'].endswith('tar.gz')]
            if len(uris) > 0:
                gogs_versions.update({parse_version(version): uris[0]})
        if len(software_list) > 0:
            max_version = parse_version(software_list[-1].version)
        else:
            max_version = parse_version('0')
        new_versions = [gogs_ver for gogs_ver in gogs_versions if gogs_ver > max_version]

        # TODO: lock distribuited repo
        logger.info(f"Downloading new versions {', '.join(map(str, new_versions))}")
        with requests.Session() as s:
            for new_version in new_versions:
                r = s.get(base_url + gogs_versions[new_version], verify=current_app.config['SSL_VERIFY'])
                filename = get_filename_from_cd(
                    r.headers.get(
                        'content-disposition')) or f"dimensigon-{gogs_versions[new_version].rsplit('/', 1)[-1]}"
                file = os.path.join(current_app.config['SOFTWARE_DIR'], filename)
                open(file, 'wb').write(r.content)

                soft = Software(name='dimensigon', version=str(new_version), family=SoftwareFamily.MIDDLEWARE,
                                filename=filename, size=r.headers.get('content-length'), checksum=md5(file))
                ssa = SoftwareServerAssociation(software=soft, server=Server.get_current(),
                                                path=current_app.config['SOFTWARE_DIR'])
                db.session.add(soft)
                db.session.add(ssa)

        db.session.commit()

    software_list: t.List = Software.query.filter_by(name='dimensigon').all()
    software_list.sort(key=lambda s: parse_version(s.version))

    if len(software_list) > 0 and parse_version(dm_version) < parse_version(software_list[-1].version):
        soft2deploy: Software = software_list[-1]
        # check if I should get software
        ssa = [ssa for ssa in soft2deploy.ssas if ssa.server == Server.get_current()]
        deployable = None
        if ssa:
            deployable = os.path.join(ssa[0].path, soft2deploy.filename)
        else:
            # get software if not in folder
            file = os.path.join(current_app.config['SOFTWARE_DIR'], soft2deploy.filename)
            if not os.path.exists(file):
                ssa = min(soft2deploy.ssas, key=lambda x: x.server.route.cost or 999999)
                logger.debug(f"Getting software from server {ssa.server.id}")
                r = requests.post(url=ssa.server.url('api_1_0.software_send'),
                                  json=pack_msg({"software_id": str(soft2deploy.id),
                                                 "dest_server_id": str(Server.get_current().id),
                                                 "dest_path": current_app.config['SOFTWARE_DIR'],
                                                 "chunk_size": 1024 * 1024 * 4,
                                                 "max_senders": os.environ.get('WORKERS', 2)},
                                                pub_key=Dimension.get_current().public,
                                                priv_key=Dimension.get_current().private),
                                  headers={'D-Destination': str(ssa.server.id)})
                r.raise_for_status()
                data = unpack_msg(r.json(), pub_key=Dimension.get_current().public,
                                  priv_key=Dimension.get_current().private)
                trans_id = data.get('transfer_id')
                logger.debug(f"Transfer ID {trans_id} generated")
                trans: Transfer = Transfer.query.get(trans_id)
                status = trans.wait_transfer(timeout=timeout_wait_transfer, refresh_interval=refresh_interval)
                if status == TransferStatus.COMPLETED:
                    deployable = os.path.join(current_app.config['SOFTWARE_DIR'], soft2deploy.filename)
                elif status in (TransferStatus.IN_PROGRESS, TransferStatus.WAITING_CHUNKS):
                    logger.debug(f"Timeout while waiting transfer ID {trans_id} to be completed")
                    raise ue.TransferTimeout()
                else:
                    logger.debug(f"Error while waiting transfer ID {trans_id} to be completed")
                    raise ue.TransferError(status)
            else:
                deployable = file
        if deployable:
            logger.info(f"Upgrading to version {soft2deploy.version}")
            stdout = open('elevator.out', 'a')
            subprocess.Popen(['python', 'elevator.py', '-d', deployable],
                             stdin=None, stdout=stdout, stderr=stdout, close_fds=True, env=os.environ)
            stdout.close()
    else:
        logger.debug(f"No version to upgrade")
