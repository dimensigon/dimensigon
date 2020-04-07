import base64
import logging
import os
import typing as t

from flask_jwt_extended import create_access_token

from dm.domain.entities import Log, Server
from dm.utils import asyncio
from dm.utils.helpers import remove_prefix
from dm.utils.pygtail import Pygtail
from dm.utils.typos import Id
from dm.web.network import async_post, HTTPBearerAuth

MAX_LINES = 10000

logger = logging.getLogger('dm.background.log_sender')


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


class LogSender:

    def __init__(self):
        self.buffer_data = None
        self.sending_data = True
        self._mapper: t.Dict[Id, t.List[_PygtailBuffer]] = {}

    @property
    def logs(self):
        return Log.query.filter_by(source_server=Server.get_current()).all()

    def update_mapper(self):
        logs = self.logs
        id2log = {log.id: log for log in logs}
        # remove logs
        for log_id in self._mapper.keys():
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

    async def send_new_data(self):

        logger.debug(f"Sending new data to servers")
        self.update_mapper()

        tasks = []

        auth = HTTPBearerAuth(create_access_token('root'))
        for log_id, pb in self._mapper.items():
            log = Log.query.get(log_id)
            for pytail in pb:
                data = pytail.fetch()
                data = data.encode() if isinstance(data, str) else data
                if log.dest_folder:
                    if pytail.file == log.target:
                        file = os.path.join(log.dest_folder, os.path.basename(log.target))
                    else:
                        file = os.path.join(log.dest_folder, remove_prefix(pytail.file, log.target).lstrip('/'))
                else:
                    file = pytail.file
                task = asyncio.create_task(
                    async_post(log.destination_server, 'api_1_0.logresource', view_data={'log_id': str(log_id)},
                               json={"file": file, 'data': base64.b64encode(data).decode('ascii')},
                               auth=auth))

                tasks.append((task, pytail, log))
                logger.debug(f"Sending data from '{pytail.file}' to '{log.destination_server}'")

        for task, pytail, log in tasks:
            response, status_code = await task
            if isinstance(response, Exception):
                logger.exception(
                    f"Unable to send log information from '{pytail.file}' to '{log.destination_server}'",
                    exc_info=response)
            else:
                if 199 < status_code < 300:
                    pytail.update_offset_file()
                    logger.debug(f"Updated offset from '{pytail.file}'")
                else:
                    logger.error(
                        f"Unable to send log information from '{pytail.file}' to '{log.destination_server}'. Error"
                        f"{response[1]}, {response[0]}")
