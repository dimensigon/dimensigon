# business functions related with business logic
import base64
import datetime
import json
import logging
import os
import subprocess
import typing as t

from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt_identity
from sqlalchemy.orm.attributes import flag_modified

from dimensigon import defaults
from dimensigon.domain.entities import Server, bypass_datamark_update, Scope, Catalog
from dimensigon.use_cases.lock import lock_scope
from dimensigon.utils.helpers import get_distributed_entities
from dimensigon.web import db, errors
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


def upgrade_catalog(catalog, check_mismatch=True):
    de = get_distributed_entities()

    if check_mismatch:
        inside = set([name for name, cls in de])
        catalog_logger.debug(f'Actual entities: {inside}')

        outside = set(catalog.keys())
        catalog_logger.debug(f'Remote entities: {outside}')

        if len(inside ^ outside) > 0:
            raise errors.CatalogMismatch(inside, outside)

    with bypass_datamark_update():
        for name, cls in de:
            if name in catalog:
                if len(catalog[name]) > 0:
                    catalog_logger.log(1,
                        f"Adding/Modifying new '{name}' entities: \n{json.dumps(catalog[name], indent=2, sort_keys=True)}")
                for dto in catalog[name]:
                    o = cls.from_json(dict(dto))
                    # force modification to update catalog last_modified_at
                    flag_modified(o, 'last_modified_at')
                    db.session.add(o)

        db.session.commit()


def upgrade_catalog_from_server(server):
    with lock_scope(Scope.UPGRADE, [server, Server.get_current()]):
        catalog_ver = db.session.query(db.func.max(Catalog.last_modified_at)).scalar()
        if catalog_ver:
            resp = get(server, 'api_1_0.catalog',
                       view_data=dict(data_mark=catalog_ver.strftime(defaults.DATEMARK_FORMAT)),
                       headers={'Authorization': 'Bearer ' + create_access_token(get_jwt_identity(),
                                                                                 expires_delta=datetime.timedelta(
                                                                                     seconds=15))})

            if resp.code and 199 < resp.code < 300:
                delta_catalog = resp.msg
                upgrade_catalog(delta_catalog)
            else:
                catalog_logger.error(f"Unable to get a valid response from server {server}: {resp}")
