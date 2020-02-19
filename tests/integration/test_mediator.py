import datetime
import uuid

from asynctest import TestCase, mock
from dm.utils.async_operator import AsyncOperator, CompletedProcess

from dm.domain.entities import Server
from dm.network import TypeMsg
from dm.use_cases.base import Scope, Token
from dm.use_cases.deployment import UndoCommand, TestOperation, Command, Execution
from dm.use_cases.exceptions import ErrorLock
from dm.use_cases.mediator import Mediator
from dm.web import create_app, db


class TestMediator(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')
        self.ao = AsyncOperator()
        self.ao.start()
        self.local = Server('Server1', '127.0.0.1', 5001, id=uuid.UUID('11111111-2222-3333-4444-555555550001'))
        self.remote = Server('Remote', '127.0.0.1', 5002, id=uuid.UUID('11111111-2222-3333-4444-555555550002'))

        with self.app.app_context():
            db.session.add(self.local)
            db.session.add(self.remote)
            db.session.commit()

    def tearDown(self) -> None:
        self.ao.stop()
        del self.ao

    def test_local_command_invocation_and_completion(self):
        date = datetime.datetime.now()
        undo_cmd = UndoCommand(
            implementation=TestOperation(code='test code'),
            params={'start_time': date, 'end_time': date, 'stdout': 'undo command'}, id_=1)
        cmd = Command(implementation=TestOperation(code='test code'), params={'start_time': date, 'end_time': date},
                      undo_implementation=undo_cmd, id_=2)

        tkn = Token(id=10000000000000000, source=f"{self.local.name}:{self.local.port}",
                    destination=f"{self.remote.name}:{self.remote.port}")

        with mock.patch('dm.network.gateway.send_message', return_value=('', 200)) as mocked_gateway:
            with mock.patch('dm.use_cases.mediator.random', side_effect=[2]) as mocked_random:
                with mock.patch('dm.utils.async_operator.time.time', return_value=0) as mocked_time:
                    mocked_time.return_value = 0

                    m = Mediator(async_operator=self.ao, interactor=mock.MagicMock(), server=self.local)

                    task_id = m.invoke_local_cmd(cmd, tkn)
                    res = self.ao.wait_tasks(task_id)
                    print(res)
                    kwargs = {'destination': tkn.source,
                              'msg_type': TypeMsg.COMPLETED_CMD,
                              'token': tkn,
                              'session': 20000000000000000,
                              'content': {'data': CompletedProcess(returndata=True, excep=None, runtime=0),
                                          'execution': {2: Execution(success=True, stdout='stdout', stderr='stderr',
                                                                     rc=0, start_time=date,
                                                                     end_time=date)}}}
                    mocked_gateway.assert_called_once_with(**kwargs)

                    m.undo_local_command(token=tkn, session=20000000000000000)
                    self.ao.wait_tasks()
                    kwargs = {'destination': tkn.source,
                              'msg_type': TypeMsg.COMPLETED_CMD,
                              'token': tkn,
                              'session': 20000000000000000,
                              'content': {'data': CompletedProcess(returndata=True, excep=None, runtime=0),
                                          'execution': {2: Execution(success=True, stdout='stdout', stderr='stderr',
                                                                     rc=0, start_time=date,
                                                                     end_time=date),
                                                        1: Execution(success=True, stdout='undo command',
                                                                     stderr='stderr',
                                                                     rc=0, start_time=date,
                                                                     end_time=date)
                                                        }}}
                    mocked_gateway.assert_called_with(**kwargs)

    def test_remote_command_invocation_and_completion(self):
        def callback_stack(stack_, data):
            stack_.append(data.returndata)

        undo_cmd = UndoCommand(implementation=TestOperation(code='test code'), id_=1, )
        cmd = Command(implementation=TestOperation(code='test code'), undo_implementation=undo_cmd)

        stack = list()
        tkn = Token(id=10000000000000000, source=str(self.local.id), destination=str(self.remote.id))
        with mock.patch('dm.network.gateway.send_message') as mocked_gateway:
            with mock.patch('dm.use_cases.mediator.random', side_effect=[1, 2]) as mocked_random:
                mocked_gateway.return_value = ('', 200)
                m = Mediator(self.ao, mock.MagicMock(), self.local)
                m.clear()  # clear mapper because is a singleton class
                m.invoke_remote_cmd(command=cmd, destination=self.remote, callback=(callback_stack, (stack,), {}))

                mocked_gateway.assert_called_with(content={'command': cmd}, destination=self.remote,
                                                  msg_type=TypeMsg.INVOKE_CMD, token=tkn)

                m.execute_callback(data=CompletedProcess(returndata={'response': 'test'}, excep=None), token=tkn,
                                   session=1)

                self.assertListEqual([{'response': 'test'}], stack)

                m.undo_remote_command(command=cmd, callback=(callback_stack, (stack,), {}))

                tkn.id = 20000000000000000

                mocked_gateway.assert_called_with(destination=self.remote, msg_type=TypeMsg.UNDO_CMD, token=tkn,
                                                  session=1)

                m.execute_callback(data=CompletedProcess(returndata={'undo_response': 'test'}, excep=None), token=tkn,
                                   session=1)

                self.assertListEqual([{'response': 'test'}, {'undo_response': 'test'}], stack)

    def test_lock(self):
        s1 = Server(name='Server1', ip='127.0.0.1', port=5001, mesh_best_route=[], id=1)
        s2 = Server(name='Server2', ip='127.0.0.1', port=5002, mesh_best_route=[], id=2)
        s3 = Server(name='Server3', ip='127.0.0.1', port=5003, mesh_best_route=[2], id=3)
        s4 = Server(name='Server4', ip='127.0.0.1', port=5004, mesh_best_route=[2, 3], id=4)
        servers = [s1, s2, s3, s4]

        m = Mediator(self.ao, None, server=self.local)
        with mock.patch('dm.network.gateway.async_send_message', return_value=('', 200,)) as mocked_send:
            m.lock_unlock('L', Scope.ORCHESTRATION, servers)
            self.assertEqual(8, mocked_send.call_count)

        side_effect = [('', 200,), ('', 200,), ('', 200,), ('', 200,), ('Server1:5001: Priority Locked', 404,),
                       ('', 200,), ('', 200,), ('', 200,)]
        with mock.patch('dm.network.gateway.async_send_message', side_effect=side_effect) as mocked_send:
            with self.assertRaises(ErrorLock) as cm:
                m.lock_unlock('L', Scope.ORCHESTRATION, servers)

            self.assertEqual(1, len(cm.exception.errors))
            self.assertEqual(cm.exception.errors[0].server, s1)
            self.assertTupleEqual(cm.exception.errors[0].args, ('Server1:5001: Priority Locked',))
            self.assertEqual(8, mocked_send.call_count)
