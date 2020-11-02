import asyncio
import base64
import logging
import multiprocessing as mp
import os
import queue
import time
import typing as t
import zlib
from concurrent.futures.thread import ThreadPoolExecutor

from dataclasses import dataclass
from sqlalchemy import orm
from sqlalchemy.orm import sessionmaker
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from dimensigon.domain.entities import File, Server
from dimensigon.use_cases.base import Process
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon

_logger = logging.getLogger('dimensigon.fileSync')

SYNC_INTERVAL = 5
# period of time process checks for new files added to the database. must be equal or bigger than SYNC_INTERVAL
FILE_WATCHES_REFRESH_PERIOD = 30
MAX_ALLOWED_ERRORS = 3
# retry blacklisted servers after RETRY_BLACKLIST seconds
RETRY_BLACKLIST = 120

FileWatchId = t.Tuple[Id, str]


class EventHandler(PatternMatchingEventHandler):

    def __init__(self, fw_id: FileWatchId, fs: 'FileSync', *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fw_id = fw_id
        self.fs = fs
        self.last_modified = time.time()

    def on_any_event(self, event: FileSystemEvent):
        if time.time() - self.last_modified > 1:
            _logger.debug(f"{event.event_type} event triggered on {event.src_path}")
            self.last_modified = time.time()
            self.fs.add(self.fw_id)


@dataclass
class BlacklistEntry:
    retries: int = 0
    blacklisted: float = None


class FileSync(Process):
    _logger = _logger

    def __init__(self, dimensigon: 'Dimensigon', shutdown_event, sync_interval=SYNC_INTERVAL,
                 file_watches_refresh_period=FILE_WATCHES_REFRESH_PERIOD, max_allowed_errors=MAX_ALLOWED_ERRORS,
                 retry_blacklist=RETRY_BLACKLIST):
        super().__init__(shutdown_event, name=self.__class__.__name__)
        self.dm = dimensigon

        # Multiprocessing
        self.queue = mp.Queue(1000)

        # Parameters
        self.sync_interval = sync_interval
        self.file_watches_refresh_period = file_watches_refresh_period
        self.max_allowed_errors = max_allowed_errors
        self.retry_blacklist = retry_blacklist

        # internals
        self._changed_files: t.Set[Id] = set()
        self._changed_servers: t.Dict[Id, t.List[Id]] = dict()
        self._file2watch: t.Dict[Id, ObservedWatch] = {}
        self._last_file_updated = None
        self._blacklist: t.Dict[t.Tuple[Id, Id], BlacklistEntry] = {}
        self.session = None
        self._server = None

    def _create_session(self):
        self.Session = sessionmaker(bind=self.dm.engine)
        return self.Session()

    @property
    def server(self) -> Server:
        if self._server is None:
            self._server = self.session.query(Server).filter_by(_me=1, deleted=0).one_or_none()
        return self._server

    @property
    def my_files_query(self):
        return self.session.query(File).filter_by(deleted=0).filter_by(
            src_server_id=self.server.id) if self.session else None
        # return File.query.filter_by(src_server_id=self._server_id)

    @property
    def file_query(self):
        return self.session.query(File).filter_by(deleted=0) if self.session else None
        # return File.query

    def get_file(self, file_id):
        return self.file_query.filter_by(id=file_id).one_or_none() if self.session else None
        # return self.file_query.filter_by(id=file_id).one_or_none()

    def _add(self, file_id: Id, server_id: Id = None):
        if server_id:
            if file_id not in self._changed_files:
                if file_id not in self._changed_servers:
                    self._changed_servers[file_id] = [server_id]
                else:
                    if server_id not in self._changed_servers[file_id]:
                        self._changed_servers[file_id].append(server_id)
        else:
            self._changed_files.add(file_id)
            if file_id in self._changed_servers:
                self._changed_servers.pop(file_id)

    def _consume_events(self):
        while not (self.queue.empty() or self._stop.is_set()):
            try:
                item = self.queue.get(block=True, timeout=1)
            except queue.Empty:
                break
            self._add(*item)

    @staticmethod
    def _read_file(file, compress=True):
        with open(file, 'rb') as fd:
            if compress:
                return base64.b64encode(zlib.compress(fd.read())).decode('utf-8')
            else:
                return base64.b64encode(fd.read()).decode('utf-8')

    async def _send_file(self, file: File, servers: t.List[Id] = None):
        try:
            content = await self._loop.run_in_executor(self._executor, self._read_file, file.target)
        except Exception as e:
            _logger.exception(f"Unable to get content from file {file.target}.")
            return

        if servers:
            server_ids = servers
            fsas = [fsa for fsa in file.destinations if fsa.destination_server.id in server_ids]
        else:
            server_ids = [fsa.destination_server.id for fsa in file.destinations]
            fsas = file.destinations

        with self.dm.flask_app.app_context():
            auth = get_root_auth()
            alive = self.dm.cluster_manager.get_alive()
            tasks = [ntwrk.async_post(fsa.destination_server, view_or_url='api_1_0.file_sync',
                                      view_data={'file_id': file.id},
                                      json=dict(file=fsa.target, data=content, force=True),
                                      auth=auth) for fsa in fsas if fsa.destination_server.id in alive]
            skipped = [fsa.destination_server.name for fsa in fsas if fsa.destination_server.id not in alive]
            if skipped:
                _logger.debug(
                    f"Following servers are skipped because we do not see them alive: {', '.join(skipped)}")
            if tasks:
                _logger.debug(
                    f"Syncing file {file} with the following servers: {', '.join([fsa.destination_server.name for fsa in fsas if fsa.destination_server.id in alive])}.")

                resp = await asyncio.gather(*tasks)
                for resp, fsa in zip(resp, fsas):
                    if not resp.ok:
                        _logger.warning(
                            f"Unable to send file {file.target} to {fsa.destination_server}. Reason: {resp}")
                        if (file.id, fsa.destination_server.id) not in self._blacklist:
                            bl = BlacklistEntry()
                            self._blacklist[(file.id, fsa.destination_server.id)] = bl
                        else:
                            bl = self._blacklist.get((file.id, fsa.destination_server.id))
                        bl.retries += 1
                        if bl.retries >= self.max_allowed_errors:
                            _logger.debug(f"Adding server {fsa.destination_server} to the blacklist.")
                            bl.blacklisted = time.time()
                    else:
                        if (file.id, fsa.destination_server.id) in self._blacklist:
                            self._blacklist.pop((file.id, fsa.destination_server.id), None)


    def _sync_files(self):
        self._consume_events()
        tasks = []
        for file_id in self._changed_files:
            f = self.get_file(file_id)
            if f:
                try:
                    f.l_mtime = os.stat(f.target).st_mtime_ns
                except FileNotFoundError:
                    pass
                else:
                    tasks.append(self._send_file(f))
        if tasks:
            try:
                self.session.commit()
            except:
                self.session.rollback()

        for file_id, server_id in list(self._blacklist.keys()):
            file = self.get_file(file_id)
            dest = self.session.query(Server).filter_by(deleted=0).filter_by(id=server_id).count()
            bl = self._blacklist[(file_id, server_id)]
            if file and dest:  # file and server in the black list may be deleted
                # if server_id in getattr(getattr(self.app, 'cluster_manager', None), 'cluster', [server_id]):
                if bl.retries < self.max_allowed_errors or time.time() - bl.blacklisted > self.retry_blacklist:
                    if file_id not in self._changed_files:
                        tasks.append(self._send_file(file, [server_id]))
            else:
                self._blacklist.pop((file_id, server_id), None)

        for file_id, server_ids in self._changed_servers.items():
            file = self.get_file(file_id)
            if file:
                tasks.append(self._send_file(file, server_ids))

        if tasks:
            try:
                self._loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=False))
            except Exception:
                _logger.exception("Error while trying to send data.")
        self._changed_files.clear()
        self._changed_servers.clear()

    def _schedule_file(self, file_id, target=None):
        if isinstance(file_id, File):
            target = file_id.target
            file_id = file_id.id
        assert target is not None
        eh = EventHandler(file_id, self, patterns=[target])
        try:
            watch = self._observer.schedule(eh, os.path.dirname(target), recursive=False)
        except FileNotFoundError:
            pass
        else:
            self._file2watch.update({file_id: watch})

    def _set_initial_modifications(self):
        for file in self.my_files_query.all():
            self._schedule_file(file)
            try:
                if os.path.exists(file.target) and os.stat(file.target).st_mtime_ns != file.l_mtime:
                    self._add(file.id, None)
            except:
                pass

    def _set_watchers(self, force=False):
        if self._last_file_updated is None or time.time() - self._last_file_updated > self.file_watches_refresh_period or force:
            self._last_file_updated = time.time()
            id2target = {f.id: f.target for f in self.my_files_query.options(orm.load_only("id", "target")).all()}
            files_from_db = set(id2target.keys())
            files_already_watching = set(self._file2watch.keys())

            file_watches_to_remove = files_already_watching - files_from_db
            file_watches_to_add = files_from_db - files_already_watching

            if file_watches_to_remove:
                _logger.debug(f"Unscheduling the following files: {file_watches_to_remove}")
                for file_id in file_watches_to_remove:
                    self._observer.unschedule(self._file2watch[file_id])
                    self._file2watch.pop(file_id)

            if file_watches_to_add:
                _logger.debug(f"Scheduling the following files: {file_watches_to_add}")
                for file_id in file_watches_to_add:
                    self._schedule_file(file_id, id2target[file_id])
                    # add for sending file for first time
                    self._add(file_id, None)

    def _main(self):
        self._executor = ThreadPoolExecutor(max_workers=max(os.cpu_count(), 4),
                                            thread_name_prefix="FileSyncThreadPool")
        self._loop = asyncio.new_event_loop()
        self._loop.set_default_executor(self._executor)
        asyncio.set_event_loop(self._loop)
        self._observer = Observer()
        self.session = self._create_session()
        self._observer.start()

        self._set_initial_modifications()
        while not self._stop.is_set():
            self._set_watchers()
            self._sync_files()

    def _shutdown(self):
        self.queue.close()
        self.queue.join_thread()
        self._observer.stop()
        self.session.close()
        self._loop.stop()
        self._loop.close()
        self._executor.shutdown()

    def add(self, file: t.Union[File, Id], server: t.Union[Server, Id] = None):
        if isinstance(file, File):
            file_id = file.id
        else:
            file_id = file
        if isinstance(server, Server):
            server_id = server.id
        else:
            server_id = server
        try:
            self.queue.put((file_id, server_id), timeout=2)
        except queue.Full:
            _logger.warning("Queue is full. Try increasing its size")
