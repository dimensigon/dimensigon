import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase, mock

from flask_jwt_extended import create_access_token

from dm.domain.entities import ActionTemplate, ActionType, Orchestration, Server
from dm.use_cases.deployment import UndoCommand, CompositeCommand, CompletedProcess, Command, \
    create_cmd_from_orchestration2, ProxyCommand, ProxyUndoCommand
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestCompositeCommand(TestCase):
    maxDiff = None

    def test_invoke_undo__stop_on_error_true(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__stop_on_error_false(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(5, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__step_stop_on_error_true(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, stop_on_error=True, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__stop_undo_on_error_true(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(4, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_invoke_undo__step_stop_undo_on_error_true(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, stop_undo_on_error=True, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(2, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_invoke_undo__step_undo_on_error_false(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=datetime.datetime.now(),
                                                                end_time=datetime.datetime.now() + datetime.timedelta(
                                                                    5 / (24 * 60 * 60)))

        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=datetime.datetime.now(),
                                                                 end_time=datetime.datetime.now() + datetime.timedelta(
                                                                     5 / (24 * 60 * 60)))

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_error, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)

        c1 = Command(implementation=mocked_imp_succ, undo_command=uc1, id_=1)
        c2 = Command(implementation=mocked_imp_error, undo_command=uc2, undo_on_error=False, id_=2)
        c3 = Command(implementation=mocked_imp_succ, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_result(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, stop_on_error=True)

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=5)
        c2 = Command(implementation=mocked_imp_error, undo_command=ccu2, undo_on_error=False, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []}, stop_on_error=True, stop_undo_on_error=False)

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.result)

        self.assertEqual(1, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)
        self.assertEqual(False, res)

        res = cc.undo()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              1: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.result)

        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

    def test_composite_command_success(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_succ, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)

        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, stop_on_error=True)

        c1 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=5)
        c2 = Command(implementation=mocked_imp_succ, undo_command=ccu2, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []}, stop_on_error=False, stop_undo_on_error=False)

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)}
                             , cc.result)
        self.assertEqual(True, res)
        self.assertEqual(2, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

    def test_composite_command_error(self):
        mocked_imp_succ = mock.Mock()
        mocked_imp_error = mock.Mock()

        start_time = datetime.datetime.now()
        end_time = datetime.datetime.now() + datetime.timedelta(5 / (24 * 60 * 60))

        mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                                start_time=start_time,
                                                                end_time=end_time)
        mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                                 start_time=start_time,
                                                                 end_time=end_time)

        uc1 = UndoCommand(implementation=mocked_imp_succ, id_=1)
        uc2 = UndoCommand(implementation=mocked_imp_succ, id_=2)
        uc3 = UndoCommand(implementation=mocked_imp_error, id_=3)
        uc4 = UndoCommand(implementation=mocked_imp_succ, id_=4)
        uc5 = UndoCommand(implementation=mocked_imp_succ, id_=5)

        executor = ThreadPoolExecutor()
        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3, uc4]}, stop_on_error=True, executor=executor)

        c6 = Command(implementation=mocked_imp_succ, undo_command=ccu1, id_=6)
        c7 = Command(implementation=mocked_imp_succ, undo_command=ccu2, id_=7)
        c8 = Command(implementation=mocked_imp_succ, undo_command=uc5, id_=8)

        cc = CompositeCommand({c6: [c7], c7: [c8]}, stop_on_error=False, stop_undo_on_error=False, executor=executor)

        res = cc.invoke()

        self.assertTrue(res)
        self.assertEqual(3, mocked_imp_succ.execute.call_count)
        self.assertEqual(0, mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertFalse(res)
        self.assertEqual(7, mocked_imp_succ.execute.call_count)
        self.assertEqual(1, mocked_imp_error.execute.call_count)

        self.assertDictEqual({1: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              2: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              3: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              4: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              7: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time),
                              8: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=start_time,
                                                  end_time=end_time)
                              }
                             , cc.result)


class TestCreateCmdFromOrchestration2(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('test'))
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # @mock.patch('dm.use_cases.deployment.create_operation', autospec=IOperationEncapsulation)
    def test_create_cmd_from_orchestration2(self):

        at = ActionTemplate(id=uuid.UUID('aaaaaaaa-1234-5678-1234-aaaaaaaa0001'), name='create dir', version=1,
                            action_type=ActionType.NATIVE, code='mkdir {dir}',
                            parameters={}, expected_output='',
                            expected_rc=0, system_kwargs={})

        o = Orchestration('Test Orchestration', 1, 'description', id=uuid.UUID('bbbbbbbb-1234-5678-1234-bbbbbbbb0001'))

        me = Server('me', port=5000, me=True, id=uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'))
        remote = Server('remote', port=5000, id=uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'))

        db.session.add_all([me, remote, o])

        s1 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0001'), undo=False, action_template=at,
                        parents=[], target=['frontend'])
        s2 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0002'), undo=True, action_template=at,
                        parents=[s1], stop_on_error=False, target=[])
        s3 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0003'), undo=False, action_template=at,
                        parents=[s1], stop_on_error=False, stop_undo_on_error=False, target=['frontend'])
        s4 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0004'), undo=True, action_template=at,
                        parents=[s3], target=[])
        s5 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0005'), undo=True, action_template=at,
                        parents=[s4], stop_on_error=True, target=[])
        s6 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0006'), undo=True, action_template=at,
                        parents=[s4, s5], target=[])
        s7 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0007'), undo=False, action_template=at,
                        parents=[s3], undo_on_error=False, target=[])
        s8 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0008'), undo=True, action_template=at,
                        parents=[s7], target=[])
        s9 = o.add_step(id=uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0009'), undo=False, action_template=at,
                        children=[s2, s3], target=['backend'])

        cc = create_cmd_from_orchestration2(o, {'dir': 'C:\\test_folder'},
                                            hosts={'all': [me, remote], 'frontend': [me], 'backend': [remote]},
                                            executor=None)


        c1, c9 = cc._dag.get_nodes_at_level(1)
        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0001')), c1.id)
        self.assertIsInstance(c1, Command)
        self.assertTrue(c1.stop_on_error)
        self.assertTrue(c1.undo_on_error)
        self.assertIsNone(c1.stop_undo_on_error)

        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0009')), c9.id)
        self.assertIsInstance(c9, Command)
        self.assertTrue(c9.stop_on_error)
        self.assertTrue(c9.undo_on_error)
        self.assertIsNone(c9.stop_undo_on_error)

        c21 = c1.undo_command
        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0002')), c21.id)
        self.assertIsInstance(c21, UndoCommand)
        self.assertFalse(c21.stop_on_error)

        c22 = c9.undo_command
        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0002')), c22.id)
        self.assertIsInstance(c22, UndoCommand)
        self.assertFalse(c22.stop_on_error)

        c3, = cc._dag.get_nodes_at_level(2)
        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0003')), c3.id)
        self.assertIsInstance(c3, Command)
        self.assertFalse(c3.stop_on_error)
        self.assertTrue(c3.undo_on_error)
        self.assertFalse(c3.stop_undo_on_error)

        self.assertTupleEqual(('undo',
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0003')), c3.undo_command.id)
        self.assertIsInstance(c3.undo_command, CompositeCommand)
        self.assertFalse(c3.undo_command.stop_on_error)
        self.assertIsNone(c3.undo_command.stop_undo_on_error)

        c4, = c3.undo_command._dag.get_nodes_at_level(1)
        self.assertIsInstance(c4, UndoCommand)
        self.assertFalse(c4.stop_on_error)

        c5, = c3.undo_command._dag.get_nodes_at_level(2)
        self.assertIsInstance(c5, UndoCommand)
        self.assertTrue(c5.stop_on_error)

        c6, = c3.undo_command._dag.get_nodes_at_level(3)
        self.assertIsInstance(c6, UndoCommand)
        self.assertFalse(c6.stop_on_error)

        cc7, = cc._dag.get_nodes_at_level(3)
        self.assertEqual(uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0007'), cc7.id)
        self.assertIsInstance(cc7, CompositeCommand)
        self.assertFalse(cc7.stop_on_error)
        self.assertFalse(cc7.stop_undo_on_error)

        c71, c72 = cc7._dag.root
        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0007')), c71.id)
        self.assertIsInstance(c71, Command)
        self.assertTrue(c71.stop_on_error)
        self.assertFalse(c71.undo_on_error)
        self.assertIsNone(c71.stop_undo_on_error)

        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0001'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0008')), c71.undo_command.id)
        self.assertIsInstance(c71.undo_command, UndoCommand)
        self.assertTrue(c71.undo_command.stop_on_error)

        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0007')), c72.id)
        self.assertIsInstance(c72, ProxyCommand)
        self.assertTrue(c72.stop_on_error)
        self.assertFalse(c72.undo_on_error)
        self.assertIsNone(c72.stop_undo_on_error)

        self.assertTupleEqual((uuid.UUID('cccccccc-1234-5678-1234-cccccccc0002'),
                               uuid.UUID('eeeeeeee-1234-5678-1234-eeeeeeee0008')), c72.undo_command.id)
        self.assertIsInstance(c72.undo_command, ProxyUndoCommand)
        self.assertTrue(c72.undo_command.stop_on_error)