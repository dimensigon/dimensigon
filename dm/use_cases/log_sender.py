import asyncio
import os
import typing as t

from dm.framework.utils.dependency_injection import Component, Inject
from dm.framework.utils.functools import reify
from dm.repositories.repositories import LogRepo

from dm.use_cases.mediator import Mediator
from dm.utils.decorators import logged

MAX_LINES = 10000


@logged
class LogSender(Component):
    log_repo: LogRepo = Inject()

    def __init__(self, container: t.Container, mediator: Mediator):
        super().__init__(container)
        self.mediator = mediator
        self.buffer_data = None
        self.sending_data = True

    @reify
    def logs(self):
        logs = [log for log in self.log_repo.all()]
        self.buffer_data = [None] * len(logs)
        return logs

    def send_new_data(self, ids: t.List[int] = None):
        if not ids:
            # TODO check for new logs added
            self.sending_data = True
        self.logger.debug(f"Sending new data to servers")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        tasks = []
        task_id = []

        for i in ids or range(len(self.logs)):
            if self.buffer_data[i] is None:
                self.buffer_data[i] = self.logs[i].readlines(max_lines=MAX_LINES)
            if self.buffer_data[i]:
                self.logger.debug(f"Sending data from '{self.logs[i].file}' to '{self.logs[i].server}'")
                data = b''.join(self.buffer_data[i]) if self.logs[i].binary else ''.join(self.buffer_data[i])
                tasks.append(self.mediator.send_data_log(os.path.basename(self.logs[i].file), self.logs[i].server,
                                                         data, self.logs[i].dest_folder))
                task_id.append(i)
            else:
                self.buffer_data[i] = None
        pool_responses = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

        loop.close()

        pending_data = []
        for i, response in zip(task_id, pool_responses):
            if isinstance(response, Exception):
                self.logger.error(
                    f"Unable to send log information to '{self.logs[i].server}' from file '{self.logs[i].file}'. "
                    f"HTTP code: {response.args[2]}. Response:\n{response.args[1]}")
            else:
                self.logger.debug(f"setting offset from '{self.logs[i].file}' to {self.logs[i]._offset}")
                self.logs[i].update_offset_file()
                if len(self.buffer_data[i]) == MAX_LINES:
                    pending_data.append(i)
                self.buffer_data[i] = None

        if pending_data:
            self.send_new_data(pending_data)
        if not ids:
            self.sending_data = False
