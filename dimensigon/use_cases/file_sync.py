import asyncio
import base64
import logging
import os
import threading
import time
import typing as t
import zlib
from concurrent.futures.process import ProcessPoolExecutor
from copy import copy

from dataclasses import dataclass
from sqlalchemy import orm
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from dimensigon.domain.entities import File, Server
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.typos import Id
from dimensigon.web import DimensigonFlask, db
from dimensigon.web import network as ntwrk

_logger = logging.getLogger('dimensigon.fileSync')

SYNC_INTERVAL = 2
# period of time process checks for new files added to the database. must be equal or bigger than SYNC_INTERVAL
FILE_WATCHES_REFRESH_PERIOD = 30
MAX_ALLOWED_ERRORS = 3
# retry blacklisted servers after RETRY_BLACKLIST seconds
RETRY_BLACKLIST = 90

FileWatchId = t.Tuple[Id, str]


class EventHandler(FileSystemEventHandler):

    def __init__(self, fw_id: FileWatchId, fs: 'FileSync') -> None:
        super().__init__()
        self.fw_id = fw_id
        self.fs = fs

    def on_modified(self, event):
        self.fs.add(self.fw_id)


@dataclass
class BlacklistEntry:
    retries: int = 0
    blacklisted: float = None


class FileSync:

    def __init__(self, app: DimensigonFlask, loop=None, executor=None, sync_interval=SYNC_INTERVAL,
                 file_watches_refresh_period=FILE_WATCHES_REFRESH_PERIOD, max_allowed_errors=MAX_ALLOWED_ERRORS,
                 retry_blacklist=RETRY_BLACKLIST):
        self.app = app
        self.loop = loop or asyncio.new_event_loop()
        self.sync_interval = sync_interval
        self.file_watches_refresh_period = file_watches_refresh_period
        self.max_allowed_errors = max_allowed_errors
        self.retry_blacklist = retry_blacklist

        self._thread = threading.Thread(target=self.run, name="FileSyncThread")
        self.executor = executor or ProcessPoolExecutor(max_workers=max(os.cpu_count(), 4))
        self.loop.set_default_executor(self.executor)
        self._lock = threading.Lock()
        self._changed_files: t.Set[Id] = set()
        self._changed_servers: t.Dict[Id, t.List[Id]] = {}
        self._stop = threading.Event()
        self._observer = Observer()
        self._file2watch: t.Dict[Id, ObservedWatch] = {}
        self._last_file_updated = None
        self._blacklist: t.Dict[t.Tuple[Id, Id], BlacklistEntry] = {}

    def add(self, file: t.Union[File, Id], server: t.Union[Server, Id] = None):
        if isinstance(file, File):
            file_id = file.id
        else:
            file_id = file
        if isinstance(server, Server):
            server_id = server.id
        else:
            server_id = server
        with self._lock:
            if server_id:
                if file_id not in self._changed_files:
                    if file_id not in self._changed_servers:
                        self._changed_servers[file_id] = [server_id]
                    else:
                        self._changed_servers[file_id].append(server_id)
            else:
                self._changed_files.add(file_id)
                if file_id in self._changed_servers:
                    self._changed_servers.pop(file_id)

    @staticmethod
    def _read_file(file, compress=True):
        with open(file, 'rb') as fd:
            if compress:
                return base64.b64encode(zlib.compress(fd.read())).decode('utf-8')
            else:
                return base64.b64encode(fd.read()).decode('utf-8')

    async def _send_file(self, file: File, servers: t.List[Id] = None):
        try:
            content = await self.loop.run_in_executor(self.executor, self._read_file, file.target)
        except Exception as e:
            _logger.exception(f"Unable to get content from file {file.target}")
            return

        db.session.refresh(file)
        if servers:
            server_ids = servers
            fsas = [fsa for fsa in file.destinations if fsa.destination_server.id in server_ids]
        else:
            server_ids = [fsa.destination_server.id for fsa in file.destinations]
            fsas = file.destinations

        tasks = [ntwrk.async_post(fsa.destination_server, view_or_url='api_1_0.fileresource',
                                  view_data={'file_id': file.id},
                                  json=dict(file=fsa.target, data=content, force=True),
                                  auth=get_root_auth()) for fsa in fsas if
                 fsa.destination_server.id in getattr(getattr(self.app, 'cluster_manager', None), 'cluster',
                                                      server_ids)]

        skipped = [fsa.destination_server.name for fsa in fsas if
                   fsa.destination_server.id not in getattr(getattr(self.app, 'cluster_manager', None), 'cluster',
                                                            server_ids)]
        if skipped:
            _logger.debug(f"Following servers are skipped because we do not see them alive: {skipped}")
        resp = await asyncio.gather(*tasks)
        for resp, fsa in zip(resp, file.destinations):
            if not resp.ok:
                _logger.warning(f"Unable to send file {file.target} to {fsa.destination_server}. Reason: {resp}")
                if (file.id, fsa.destination_server.id) not in self._blacklist:
                    bl = BlacklistEntry()
                    self._blacklist[(file.id, fsa.destination_server.id)] = bl
                else:
                    bl = self._blacklist.get((file.id, fsa.destination_server.id))
                bl.retries += 1
                if bl.retries >= self.max_allowed_errors:
                    bl.blacklisted = time.time()
            else:
                if (file.id, fsa.destination_server.id) in self._blacklist:
                    self._blacklist.pop((file.id, fsa.destination_server.id), None)

    def _sync_files(self):
        with self._lock:
            changed_files = copy(self._changed_files)
            changed_servers = copy(self._changed_servers)
            self._changed_files.clear()
            self._changed_servers.clear()

        tasks = []
        for file_id in changed_files:
            f = File.query.options(orm.joinedload('destinations')).get(file_id)
            if f:
                f.l_mtime = os.stat(f.target).st_mtime_ns
                tasks.append(self._send_file(f))
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            _logger.error("Unable to save modification time data.")

        for file_id, server_id in list(self._blacklist.keys()):
            file = File.query.get(file_id)
            dest = Server.query.get(server_id)
            bl = self._blacklist[(file_id, server_id)]
            if file and dest:
                if server_id in getattr(getattr(self.app, 'cluster_manager', None), 'cluster', [server_id]):
                    if bl.retries < self.max_allowed_errors or time.time() - bl.blacklisted > self.retry_blacklist:
                        if file_id not in self._changed_files:
                            tasks.append(self._send_file(file, [dest]))
            else:
                self._blacklist.pop((file_id, server_id), None)

        for file_id, server_ids in changed_servers.items():
            file = File.query.get(file_id)
            if file:
                tasks.append(self._send_file(file, server_ids))

        if tasks:
            try:
                self.loop.run_until_complete(asyncio.gather(*tasks))
            except Exception:
                _logger.exception("Error while trying to send data.")

    def _set_initial_modifications(self):
        for file in File.query.all():
            if os.stat(file.target) != file.l_mtime:
                self.add(file.id)

    def _set_watchers(self, force=False):
        if self._last_file_updated is None or time.time() - self._last_file_updated > self.file_watches_refresh_period or force:
            self._last_file_updated = time.time()
            id2target = {f.id: f.target for f in File.query.options(orm.load_only("id", "target")).all()}
            files_from_db = set(id2target.keys())
            files_already_watching = set(self._file2watch.keys())

            file_watches_to_remove = files_already_watching - files_from_db
            file_watches_to_add = files_from_db - files_already_watching

            for file_id in file_watches_to_remove:
                self._observer.unschedule(self._file2watch[file_id])
                self._file2watch.pop(file_id)

            for file_id in file_watches_to_add:
                try:
                    watch = self._observer.schedule(EventHandler(file_id, self), id2target[file_id], recursive=False)
                except FileNotFoundError:
                    pass
                else:
                    self._file2watch.update({file_id: watch})
                    # add for sending file for first time
                    self.add(file_id)

    def start(self):
        self._observer.start()
        self._thread.start()

    def run(self):
        asyncio.set_event_loop(self.loop)
        with self.app.app_context():
            self._set_initial_modifications()
            while not self._stop.is_set():
                self._set_watchers()
                self._sync_files()
                self._stop.wait(self.sync_interval)

    def stop(self, timeout=None):
        _logger.debug("Stopping Observer.")
        self._observer.stop()
        _logger.debug("Stopping FileSyncThread.")
        self._stop.set()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            _logger.warning("FileSyncThread is still alive.")
