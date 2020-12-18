import base64
import logging
import os
import queue
import time
import typing as t
import zlib
from collections import OrderedDict
from concurrent.futures.thread import ThreadPoolExecutor

from dataclasses import dataclass
from sqlalchemy import orm
from sqlalchemy.orm import sessionmaker
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from dimensigon import defaults
from dimensigon.domain.entities import File, Server, Log, FileServerAssociation
from dimensigon.domain.entities.log import Mode
from dimensigon.use_cases.cluster import NewEvent, AliveEvent
from dimensigon.use_cases.mptools import MPQueue, TimerWorker
from dimensigon.utils import asyncio
from dimensigon.utils.helpers import remove_root
from dimensigon.utils.pygtail import Pygtail
from dimensigon.utils.typos import Id
from dimensigon.web import network as ntwrk, get_root_auth

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon

_logger = logging.getLogger('dm.FileSync')
_log_logger = logging.getLogger('dm.logfed')

MAX_LINES = 10000  # max lines readed from a log
# period of time process checks for new files added to the database. must be equal or bigger than defaults.
FILE_WATCHES_REFRESH_PERIOD = 30
MAX_ALLOWED_ERRORS = 2  # max allowed errors to consider a node blacklisted
RETRY_BLACKLIST = 300  # retry blacklisted servers after RETRY_BLACKLIST seconds


class _PygtailBuffer(Pygtail):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffer = None

    def fetch(self):
        if self._buffer:
            return self._buffer
        else:
            self._buffer = ''.join(self.readlines(max_lines=MAX_LINES))
        return self._buffer

    def update_offset_file(self):
        self._buffer = None
        super().update_offset_file()


FileWatchId = t.Tuple[Id, str]


class WatchdogEventHandler(PatternMatchingEventHandler):

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


class FileSync(TimerWorker):
    ###########################
    # START Class Inheritance #
    def init_args(self, dimensigon: 'Dimensigon', file_sync_period=defaults.FILE_SYNC_PERIOD,
                  file_watches_refresh_period=FILE_WATCHES_REFRESH_PERIOD, max_allowed_errors=MAX_ALLOWED_ERRORS,
                  retry_blacklist=RETRY_BLACKLIST):
        self.dm = dimensigon

        # Multiprocessing
        self.queue = MPQueue()

        # Parameters
        self.INTERVAL_SECS = file_sync_period
        self.file_watches_refresh_period = file_watches_refresh_period
        self.max_allowed_errors = max_allowed_errors
        self.retry_blacklist = retry_blacklist

        # internals
        self._changed_files: t.Set[Id] = set()  # list of changed files to be sent
        self._changed_servers: t.Dict[Id, t.List[Id]] = dict()
        self._file2watch: t.Dict[Id, ObservedWatch] = {}
        self._last_file_updated = None
        self._blacklist: t.Dict[t.Tuple[Id, Id], BlacklistEntry] = {}
        self._blacklist_log: t.Dict[t.Tuple[Id, Id], BlacklistEntry] = {}
        self.session = None
        self._server = None
        self._loop = None

        # log variables
        self._mapper: t.Dict[Id, t.List[_PygtailBuffer]] = {}

    def startup(self):
        self._executor = ThreadPoolExecutor(max_workers=max(os.cpu_count(), 4),
                                            thread_name_prefix="FileSyncThreadPool")
        self._observer = Observer()
        self.session = self._create_session()
        self._observer.start()

        self._set_initial_modifications()
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.dispatcher.listen([NewEvent, AliveEvent], lambda x: self.add(None, x.args[0]))

    def shutdown(self):
        self.session.close()
        self._observer.stop()
        self._executor.shutdown()

    def main_func(self):
        # collect new File events
        while True:
            item = self.queue.safe_get()
            if item:
                self._add(*item)
            else:
                break
        self._set_watchers()
        self._sync_files()

        # send log data
        self._send_new_data()

    # END Class Inheritance #
    #########################

    ############################
    # INIT Interface functions #
    def add(self, file: t.Union[File, Id] = None, server: t.Union[Server, Id] = None):
        if isinstance(file, File):
            file_id = file.id
        else:
            file_id = file
        if isinstance(server, Server):
            server_id = server.id
        else:
            server_id = server
        try:
            self.queue.safe_put((file_id, server_id), timeout=2)
        except queue.Full:
            self.logger.warning("Queue is full. Try increasing its size")

    # END Interface functions  #
    ############################

    ##############################
    # INNER methods & attributes #
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

    def _add(self, file_id: Id = None, server_id: Id = None):
        if server_id:
            if file_id is None:
                # new server alive, send all files
                for fsa in self.session.query(FileServerAssociation).filter_by(dst_server_id=server_id, deleted=0).join(
                        File).filter_by(src_server_id=self.server.id).all():
                    if not (getattr(fsa.file, 'deleted', True) or fsa.destination_server.deleted):
                        mtime = os.stat(fsa.target).st_mtime_ns
                        if fsa.l_mtime != mtime:
                            self._add(fsa.file.id, fsa.destination_server.id)
            elif file_id not in self._changed_files:
                # send data to a specific server
                if file_id not in self._changed_servers:
                    self._changed_servers[file_id] = [server_id]
                else:
                    if server_id not in self._changed_servers[file_id]:
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
            content = await self._loop.run_in_executor(self._executor, self._read_file, file.target)
        except Exception as e:
            self.logger.exception(f"Unable to get content from file {file.target}.")
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
                self.logger.debug(
                    f"Following servers are skipped because we do not see them alive: {', '.join(skipped)}")
            if tasks:
                self.logger.debug(
                    f"Syncing file {file} with the following servers: {', '.join([fsa.destination_server.name for fsa in fsas if fsa.destination_server.id in alive])}.")

                resp = await asyncio.gather(*tasks)
                for resp, fsa in zip(resp, fsas):
                    if not resp.ok:
                        self.logger.warning(
                            f"Unable to send file {file.target} to {fsa.destination_server}. Reason: {resp}")
                        if (file.id, fsa.destination_server.id) not in self._blacklist:
                            bl = BlacklistEntry()
                            self._blacklist[(file.id, fsa.destination_server.id)] = bl
                        else:
                            bl = self._blacklist.get((file.id, fsa.destination_server.id))
                        bl.retries += 1
                        if bl.retries >= self.max_allowed_errors:
                            self.logger.debug(f"Adding server {fsa.destination_server} to the blacklist.")
                            bl.blacklisted = time.time()
                    else:
                        if (file.id, fsa.destination_server.id) in self._blacklist:
                            self._blacklist.pop((file.id, fsa.destination_server.id), None)
                        fsa.l_mtime = file.l_mtime
                try:
                    self.session.commit()
                except:
                    self.session.rollback()

    def _sync_files(self):
        coros = []
        for file_id in self._changed_files:
            f = self.get_file(file_id)
            if f:
                try:
                    f.l_mtime = os.stat(f.target).st_mtime_ns
                except FileNotFoundError:
                    pass
                else:
                    coros.append(self._send_file(f))
        if coros:
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
                        coros.append(self._send_file(file, [server_id]))
            else:
                self._blacklist.pop((file_id, server_id), None)

        for file_id, server_ids in self._changed_servers.items():
            file = self.get_file(file_id)
            if file:
                coros.append(self._send_file(file, server_ids))

        if coros:
            try:
                self._loop.run_until_complete(asyncio.gather(*coros, return_exceptions=False))
            except Exception:
                self.logger.exception("Error while trying to send data.")
        self._changed_files.clear()
        self._changed_servers.clear()

    def _schedule_file(self, file_id, target=None):
        if isinstance(file_id, File):
            target = file_id.target
            file_id = file_id.id
        assert target is not None
        weh = WatchdogEventHandler(file_id, self, patterns=[target])
        try:
            watch = self._observer.schedule(weh, os.path.dirname(target), recursive=False)
        except FileNotFoundError:
            pass
        else:
            self._file2watch.update({file_id: watch})

    def _set_initial_modifications(self):
        for file in self.my_files_query.all():
            self._schedule_file(file)
            try:
                if os.path.exists(file.target):
                    mtime = os.stat(file.target).st_mtime_ns
                    if mtime != file.l_mtime:
                        self._add(file.id, None)
                    else:
                        for fsa in file.destinations:
                            if fsa.l_mtime != mtime:
                                self._add(file.id, fsa.destination_server.id)
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
                self.logger.debug(f"Unscheduling the following files: {file_watches_to_remove}")
                for file_id in file_watches_to_remove:
                    self._observer.unschedule(self._file2watch[file_id])
                    self._file2watch.pop(file_id)

            if file_watches_to_add:
                self.logger.debug(f"Scheduling the following files: {file_watches_to_add}")
                for file_id in file_watches_to_add:
                    self._schedule_file(file_id, id2target[file_id])
                    # add for sending file for first time
                    self._add(file_id, None)

    @property
    def my_logs(self):
        return self.session.query(Log).filter_by(source_server=Server.get_current(session=self.session)).all()

    def update_mapper(self):
        logs = self.my_logs
        id2log = {log.id: log for log in logs}
        # remove logs
        for log_id in list(self._mapper.keys()):
            if log_id not in id2log:
                del self._mapper[log_id]

        # add new logs
        for log in logs:
            if log.id not in self._mapper:
                self._mapper[log.id] = []
            self.update_pytail_objects(log, self._mapper[log.id])

    def update_pytail_objects(self, log: Log, pytail_list: t.List):
        if os.path.isfile(log.target):
            if len(pytail_list) == 0:
                filename = '.' + os.path.basename(log.target) + '.offset'
                path = os.path.dirname(log.target)
                offset_file = self.dm.config.path(defaults.OFFSET_DIR, remove_root(path), filename)
                if not os.path.exists(offset_file):
                    _log_logger.debug(f"creating offset file {offset_file}")
                    os.makedirs(os.path.dirname(offset_file), exist_ok=True)
                pytail_list.append(
                    _PygtailBuffer(file=log.target, offset_mode='manual', offset_file=offset_file))
        else:
            for folder, dirnames, filenames in os.walk(log.target):
                for filename in filenames:
                    if log._re_include.search(filename) and not log._re_exclude.search(filename):
                        file = os.path.join(folder, filename)
                        offset_file = os.path.join(folder, '.' + filename + '.offset')
                        if not any(map(lambda p: p.file == file, pytail_list)):
                            pytail_list.append(
                                _PygtailBuffer(file=file, offset_mode='manual', offset_file=offset_file))
                if not log.recursive:
                    break
                new_dirnames = []
                for dirname in dirnames:
                    if log._re_include.search(dirname) and not log._re_exclude.search(dirname):
                        new_dirnames.append(dirname)
                dirnames[:] = new_dirnames

    def _send_new_data(self):
        self.update_mapper()
        tasks = OrderedDict()

        for log_id, pb in self._mapper.items():
            log = self.session.query(Log).get(log_id)
            for pytail in pb:
                data = pytail.fetch()
                data = data.encode() if isinstance(data, str) else data
                if data and log.destination_server.id in self.dm.cluster_manager.get_alive():
                    if log.mode == Mode.MIRROR:
                        file = pytail.file
                    elif log.mode == Mode.REPO_ROOT:
                        path_to_remove = os.path.dirname(log.target)
                        relative = os.path.relpath(pytail.file, path_to_remove)
                        file = os.path.join('{LOG_REPO}', relative)
                    elif log.mode == Mode.FOLDER:
                        path_to_remove = os.path.dirname(log.target)
                        relative = os.path.relpath(pytail.file, path_to_remove)
                        file = os.path.join(log.dest_folder, relative)
                    else:
                        def get_root(dirname):
                            new_dirname = os.path.dirname(dirname)
                            if new_dirname == dirname:
                                return dirname
                            else:
                                return get_root(new_dirname)

                        relative = os.path.relpath(pytail.file, get_root(pytail.file))
                        file = os.path.join('{LOG_REPO}', relative)
                    with self.dm.flask_app.app_context():
                        auth = get_root_auth()

                    task = ntwrk.async_post(log.destination_server, 'api_1_0.logresource',
                                            view_data={'log_id': str(log_id)},
                                            json={"file": file,
                                                  'data': base64.b64encode(zlib.compress(data)).decode('ascii'),
                                                  "compress": True},
                                            auth=auth)

                    tasks[task] = (pytail, log)
                    _log_logger.debug(f"Task sending data from '{pytail.file}' to '{log.destination_server}' prepared")

        if tasks:
            with self.dm.flask_app.app_context():
                responses = asyncio.run(asyncio.gather(*list(tasks.keys())))

            for task, resp in zip(tasks.keys(), responses):
                pytail, log = tasks[task]
                if resp.ok:
                    pytail.update_offset_file()
                    _log_logger.debug(f"Updated offset from '{pytail.file}'")
                    if log.id not in self._blacklist:
                        self._blacklist_log.pop(log.id, None)
                else:
                    _log_logger.error(
                        f"Unable to send log information from '{pytail.file}' to '{log.destination_server}'. Error: {resp}")
                    if log.id not in self._blacklist:
                        bl = BlacklistEntry()
                        self._blacklist_log[log.id] = bl
                    else:
                        bl = self._blacklist_log.get(log.id)
                    bl.retries += 1
                    if bl.retries >= self.max_allowed_errors:
                        _log_logger.debug(f"Adding server {log.destination_server.id} to the blacklist.")
                        bl.blacklisted = time.time()
