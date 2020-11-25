import base64
import logging
import os
import time
import typing as t
import zlib

from sqlalchemy.orm import sessionmaker

from dimensigon.domain.entities import Log, Server
from dimensigon.domain.entities.log import Mode
from dimensigon.use_cases.base import Process
from dimensigon.use_cases.helpers import get_root_auth
from dimensigon.utils import asyncio
from dimensigon.utils.pygtail import Pygtail
from dimensigon.utils.typos import Id
from dimensigon.web.network import async_post

if t.TYPE_CHECKING:
    from dimensigon.core import Dimensigon

MAX_LINES = 10000

_logger = logging.getLogger('dm.log_sender')


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


class LogSender(Process):
    _logger = _logger

    def __init__(self, dimensigon: 'Dimensigon'):
        super().__init__(dimensigon.shutdown_event, name='LogSender')
        self.dm = dimensigon
        self.Session = sessionmaker(bind=self.dm.engine)
        self.buffer_data = None
        self.sending_data = True
        self._mapper: t.Dict[Id, t.List[_PygtailBuffer]] = {}

    def _create_session(self):
        self.Session = sessionmaker(bind=self.dm.engine)
        return self.Session()

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
        # TODO: handle when target does not exist
        if os.path.isfile(log.target):
            if len(pytail_list) == 0:
                filename = '.' + os.path.basename(log.target) + '.offset'
                path = os.path.dirname(log.target)
                offset_file = os.path.join(path, filename)
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

    async def _send_new_data(self):
        self.update_mapper()
        tasks = []

        for log_id, pb in self._mapper.items():
            log = self.session.query(Log).get(log_id)
            for pytail in pb:
                data = pytail.fetch()
                data = data.encode() if isinstance(data, str) else data
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
                task = asyncio.create_task(
                    async_post(log.destination_server, 'api_1_0.logresource', view_data={'log_id': str(log_id)},
                               json={"file": file, 'data': base64.b64encode(zlib.compress(data)).decode('ascii'),
                                     "compress": True},
                               auth=auth))

                tasks.append((task, pytail, log))
                _logger.debug(f"Task sending data from '{pytail.file}' to '{log.destination_server}' prepared")

        for task, pytail, log in tasks:
            response = await task
            if response.ok:
                pytail.update_offset_file()
                _logger.debug(f"Updated offset from '{pytail.file}'")
            else:
                if response.exception:
                    _logger.exception(
                        f"Unable to send log information from '{pytail.file}' to '{log.destination_server}'",
                        exc_info=response)
                else:
                    _logger.error(
                        f"Unable to send log information from '{pytail.file}' to '{log.destination_server}'. Error:"
                        f"{response[1]}, {response[0]}")

    def _main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self.session = self._create_session()

        start = time.time()
        while not self._stop.is_set():
            try:
                time.sleep(0.2)
            except Exception:
                break
            if time.time() - start > 30:
                start = time.time()
                self._loop.run_until_complete(self._send_new_data())

    def _shutdown(self):
        self.session.close()
        self._loop.stop()
        self._loop.close()
