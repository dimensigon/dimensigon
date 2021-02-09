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


class BaseCatalogException(errors.BaseError):
    """Base Class Exception"""


class NewVersionFound(BaseCatalogException):
    """Exception raised if new version found"""


class NoServerFound(BaseCatalogException):
    """No server with high catalog found"""


class NoNeighbourHealtchcheckFound(BaseCatalogException):
    """No healthcheck found server with high catalog found"""


class CatalogFetchError(BaseCatalogException):
    """Unable to fetch catalog from server"""


class HealthCheckMismatch(errors.BaseError):
    status_code = 500

    def __init__(self, expected: t.Dict[str, str], actual: t.Dict[str, str]):
        self.expected = expected
        self.actual = actual

    def _format_error_msg(self) -> str:
        return "Healtcheck response does not match with the server requested"


class CatalogMismatch(errors.BaseError):
    status_code = 500

    def __init__(self, local_entities, remote_entities):
        self.local_entities = local_entities
        self.remote_entities = remote_entities

    def _format_error_msg(self) -> str:
        return "List entities do not match"


def update_db_catalog(catalog, check_mismatch=True, logger=None):
    de = get_distributed_entities()

    if check_mismatch:
        inside = set([name for name, cls in de])
        logger.debug(f'Actual entities: {inside}') if logger else None

        outside = set(catalog.keys())
        logger.debug(f'Remote entities: {outside}') if logger else None

        if len(inside ^ outside) > 0:
            raise CatalogMismatch(inside, outside)

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
        self._server = None

    def main_func(self):
        with self._update_lock:
            with self.dm.flask_app.app_context():
                self._updating.set()
                try:
                    self.upgrade_process()
                except NewVersionFound as e:
                    self.logger.info(f'Found mayor version on server {e.args[0]}. Upgrade version first')
                except NoServerFound as e:
                    pass
                except CatalogFetchError as e:
                    self.logger.error(f'Error fetching catalog from {e.args[0].server}: {e.args[0]}')
                except (KeyboardInterrupt, TerminateInterrupt):
                    pass
                except Exception as e:
                    self.logger.exception("Exception while trying to execute catalog update")
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

    def upgrade_process(self):
        self.logger.debug("Starting check catalog from neighbours")
        # cluster information
        cluster_hearthbeat_id = get_now().strftime(defaults.DATETIME_FORMAT)
        # check version update before catalog update to match database revision
        data = asyncio.run(self._async_get_neighbour_healthcheck(cluster_hearthbeat_id))
        if data:
            self.check_new_version(data)
            self.catalog_update(data)
        else:
            raise NoServerFound()

    @property
    def server(self) -> Server:
        if self._server is None:
            self._server = Server.query.get(self.dm.server_id)
        return self._server

    @property
    def catalog_ver(self) -> dt.datetime:
        return db.session.query(db.func.max(Catalog.last_modified_at)).scalar()

    async def _async_get_neighbour_healthcheck(self, cluster_heartbeat_id: str = None) -> t.Dict[
        Server, dict]:

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
                    e = HealthCheckMismatch(
                        expected={'id': str(server.id), 'name': server.name},
                        actual=resp.msg.get('server', {}))
                    self.logger.warning(str(e))
                else:
                    server_responses.update({server: resp.msg})
            else:
                self.logger.warning(f"Unable to get Healthcheck from server {server.name}: {resp}")
        return server_responses

    def check_new_version(self, data: t.Dict[Server, dict]):
        mayor_version, mayor_server = None, None
        for server, hc in data.items():
            remote_version = parse_version(hc['version'])
            if remote_version > parse_version(__version__):
                if mayor_version is None or mayor_version < remote_version:
                    mayor_version, mayor_server = remote_version, server
        if mayor_version:
            raise NewVersionFound(str(mayor_server))

    def catalog_update(self, data: t.Dict[Server, dict]):
        reference_server = None
        if self.catalog_ver:
            for server, hc_msg in data.items():

                new_catalog_ver = dt.datetime.strptime(hc_msg['catalog_version'],
                                                       defaults.DATEMARK_FORMAT)
                if new_catalog_ver > self.catalog_ver:
                    reference_server = server
            if reference_server:
                self.logger.info(f"New catalog found from server {reference_server.name}: {self.catalog_ver}")
                self._update_catalog_from_server(reference_server)
            else:
                raise NoServerFound()

    def _update_catalog_from_server(self, server):
        with lock_scope(Scope.UPGRADE, [self.server]):
            resp = ntwrk.get(server, 'api_1_0.catalog',
                             view_data=dict(data_mark=self.catalog_ver.strftime(defaults.DATEMARK_FORMAT)),
                             auth=get_root_auth())

            if resp.code and 199 < resp.code < 300:
                delta_catalog = resp.msg
                self.db_update_catalog(delta_catalog)
            else:
                raise CatalogFetchError(resp)

    def db_update_catalog(self, catalog, check_mismatch=True):
        update_db_catalog(catalog, check_mismatch=check_mismatch, logger=self.logger)
