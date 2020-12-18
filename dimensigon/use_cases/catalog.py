import datetime as dt
import json
import multiprocessing as mp
import time
import typing as t

from pkg_resources import parse_version
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from dimensigon import __version__
from dimensigon import defaults
from dimensigon.domain.entities import bypass_datamark_update, Scope, Server, Catalog
from dimensigon.use_cases import mptools as mpt
from dimensigon.use_cases.lock import lock_scope
from dimensigon.use_cases.mptools import TerminateInterrupt
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import get_distributed_entities, get_now
from dimensigon.web import errors, db, get_root_auth
from dimensigon.web import network as ntwrk

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon


def update_db_catalog(catalog, check_mismatch=True, logger=None):
    de = get_distributed_entities()

    if check_mismatch:
        inside = set([name for name, cls in de])
        logger.debug(f'Actual entities: {inside}') if logger else None

        outside = set(catalog.keys())
        logger.debug(f'Remote entities: {outside}') if logger else None

        if len(inside ^ outside) > 0:
            raise errors.CatalogMismatch(inside, outside)

    db.session.flush()
    with bypass_datamark_update():
        for name, cls in de:
            if name in catalog:
                if len(catalog[name]) > 0:
                    logger.log(1, f"Adding/Modifying new '{name}' entities: \n"
                                  f"{json.dumps(catalog[name], indent=2, sort_keys=True)}") if logger else None
                for dto in catalog[name]:
                    o = cls.from_json(dict(dto))
                    # force modification to update catalog last_modified_at
                    flag_modified(o, 'last_modified_at')
                    db.session.add(o)

        db.session.commit()

class CatalogManager(mpt.TimerWorker):
    INTERVAL_SECS = 5 * 60

    ###########################
    # START Class Inheritance #
    def init_args(self, dimensigon: 'Dimensigon', interval_secs=defaults.CATALOG_REFRESH_PERIOD):
        self.dm = dimensigon
        self.Session = sessionmaker(bind=self.dm.engine)
        self.INTERVAL_SECS = interval_secs
        self._catalog_ver = None
        self._updating = mp.Event()
        self._update_lock = mp.Lock()

    def main_func(self):
        with self._update_lock:
            self._updating.set()
            try:
                with self.dm.flask_app.app_context():
                    self.logger.debug("Starting check catalog from neighbours")
                    # cluster information
                    cluster_hearthbeat_id = get_now().strftime(defaults.DATETIME_FORMAT)
                    # check version update before catalog update to match database revision
                    data = asyncio.run(self._async_get_neighbour_catalog_data_mark(cluster_hearthbeat_id))
                    if not self.upgrade_version(data):
                        self.catalog_update(data)
            except Exception as e:
                self.logger.exception("Exception while trying to execute catalog update")
            except (KeyboardInterrupt, TerminateInterrupt):
                pass
            finally:
                self._updating.clear()

    # END Class Inheritance #
    #########################

    ############################
    # INIT Interface functions #
    def force_catalog_update(self):
        if self._updating.is_set():
            return None
        else:
            self.next_time = None
            self.main_func()
            self.next_time = time.time() + self.INTERVAL_SECS
            return self.catalog_ver

    # END Interface functions  #
    ############################

    ##############################
    # INNER methods & attributes #

    # @property
    # def session(self):
    #     if not hasattr(self, '_session') or self._session is None:
    #         self._session = self.Session()
    #     return self._session

    @property
    def server(self) -> Server:
        if self._server is None:
            self._server = Server.query.get(self.dm.server_id)
        return self._server

    @property
    def catalog_ver(self) -> dt.datetime:
        return db.session.query(db.func.max(Catalog.last_modified_at)).scalar()

    def upgrade_version(self, data: t.Dict[Server, ntwrk.Response]):
        mayor_version, mayor_server = None, None
        for server, response in data.items():
            if response.code == 200 and 'version' in response.msg:
                remote_version = parse_version(response.msg['version'])
                if remote_version > parse_version(__version__):
                    if mayor_version is None or mayor_version < remote_version:
                        mayor_version, mayor_server = remote_version, server
        if mayor_version:
            self.logger.info(f'Found mayor version on server {mayor_server}. Upgrade version first')
            # file, v = get_software(mayor_server, get_root_auth())
            # if file:
            #     run_elevator(file, mayor_version, self.logger)
            #     return True
        return False

    async def _async_get_neighbour_catalog_data_mark(self, cluster_heartbeat_id: str = None) -> t.Dict[
        Server, ntwrk.Response]:

        server_responses = {}
        servers = Server.get_neighbours()
        self.logger.debug(f"Neighbour servers to check: {', '.join([s.name for s in servers])}")

        auth = get_root_auth()
        if cluster_heartbeat_id is None:
            cluster_heartbeat_id = get_now().strftime(defaults.DATETIME_FORMAT)

        cos = [ntwrk.async_post(server, 'root.healthcheck',
                                json={'me': self.dm.server_id,
                                      'heartbeat': cluster_heartbeat_id},
                                auth=auth) for server in servers]
        responses = await asyncio.gather(*cos)
        for server, resp in zip(servers, responses):
            if resp.ok:
                id_response = resp.msg.get('server', {}).get('id', '')
                if id_response and str(server.id) != id_response:
                    resp.exception = errors.HealthCheckMismatch(
                        expected={'id': str(server.id), 'name': server.name},
                        actual=resp.msg.get('server', {}))
                    resp.msg = None
                    resp.code = None
            else:
                self.logger.warning(f"Unable to get Healthcheck from server {server.name}: {resp}")

        return server_responses

    def catalog_update(self, data: t.Dict[Server, ntwrk.Response]):
        reference_server = None
        if self.catalog_ver:
            for server, response in data.items():
                if response.code == 200 and 'catalog_version' in response.msg:
                    new_catalog_ver = dt.datetime.strptime(response.msg['catalog_version'],
                                                           defaults.DATEMARK_FORMAT)
                    if new_catalog_ver > self.catalog_ver:
                        if response.msg['version'] == __version__:
                            reference_server = server
                        else:
                            self.logger.debug(
                                f"Server {server} has different software version {response.msg['version']}")
                else:
                    msg = f"Error while trying to get healthcheck from server {server.name}. "
                    if response.code:
                        msg = msg + f"Response from server (code {response.code}): {response.msg}"
                    else:
                        msg = msg + f"Exception: {response.code}"
                    self.logger.warning(msg)
            if reference_server:
                self.logger.info(f"New catalog found from server {reference_server.name}: {self.catalog_ver}")
                self._update_catalog_from_server(reference_server)
            else:
                self.logger.debug(f"No server with higher catalog found")

    def _update_catalog_from_server(self, server):
        with lock_scope(Scope.UPGRADE, [self.server]):
            resp = ntwrk.get(server, 'api_1_0.catalog',
                             view_data=dict(data_mark=self.catalog_ver.strftime(defaults.DATEMARK_FORMAT)),
                             auth=get_root_auth())

            if resp.code and 199 < resp.code < 300:
                delta_catalog = resp.msg
                self.db_update_catalog(delta_catalog)
            else:
                self.logger.error(f"Unable to get a valid response from server {server}: {resp}")

    def db_update_catalog(self, catalog, check_mismatch=True):
        update_db_catalog(catalog, check_mismatch=check_mismatch, logger=self.logger)
