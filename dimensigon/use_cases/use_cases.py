# business functions related with business logic
import base64
import logging
import os
import subprocess
import typing as t

from flask import current_app

from dimensigon.domain.entities import Server
from dimensigon.web.network import get

catalog_logger = logging.getLogger('dm.catalog')


def run_elevator(file, new_version, logger):
    logger.info(f"Upgrading to version {new_version}")
    stdout = open('elevator.out', 'a')
    cmd = ['python', 'elevator.py', 'upgrade', file, str(new_version)]
    logger.debug(f"Running command {' '.join(cmd)}")
    subprocess.Popen(cmd, stdin=None, stdout=stdout, stderr=stdout, close_fds=True, env=os.environ)
    stdout.close()


def get_software(server: Server, auth) -> t.Tuple[str, str]:
    resp, code = get(server, 'api_1_0.software_dimensigon', auth=auth)
    if code == 200:
        content = base64.b64decode(resp.get('content').encode('ascii'))

        file = os.path.join(current_app.config['SOFTWARE_REPO'], 'dimensigon', resp.get('filename'))
        with open(file, 'wb') as fh:
            fh.write(content)
        return file, resp.get('version')
    else:
        return None, None
