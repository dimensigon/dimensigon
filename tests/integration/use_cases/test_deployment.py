import datetime
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase, mock

from flask_jwt_extended import create_access_token

from dimensigon import defaults
from dimensigon.domain.entities import ActionTemplate, ActionType, Orchestration, Server
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.use_cases.deployment import UndoCommand, CompositeCommand, CompletedProcess, Command, \
    create_cmd_from_orchestration, ProxyCommand, ProxyUndoCommand, validate_input_chain
from dimensigon.utils.var_context import Context
from dimensigon.web import create_app, db, errors
from tests import base

START = defaults.INITIAL_DATEMARK
END = defaults.INITIAL_DATEMARK + datetime.timedelta(seconds=1)


class TestCompositeCommand(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.mock_context = mock.Mock()
        self.mock_context.keys.return_value = {}
        self.set_mocks()

    def set_mocks(self, start=START, end=END):
        self.mocked_imp_succ = mock.Mock()
        self.mocked_imp_error = mock.Mock()

        self.mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr',
                                                                     rc=0,
                                                                     start_time=start,
                                                                     end_time=end)

        self.mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr',
                                                                      rc=0,
                                                                      start_time=start,
                                                                      end_time=end)

    def test_invoke_undo__stop_on_error_true(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__stop_on_error_false(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(2, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(5, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__step_stop_on_error_true(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2,
                     stop_on_error=True, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(3, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_invoke_undo__stop_undo_on_error_true(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_error, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=False, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(2, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(4, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(2, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_invoke_undo__step_stop_undo_on_error_true(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_error, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2,
                     stop_undo_on_error=True, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(2, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

    def test_invoke_undo__step_undo_on_error_false(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_error, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc1, id_=1)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=uc2,
                     undo_on_error=False, id_=2)
        c3 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc3, id_=3)

        cc1 = CompositeCommand({c1: [c2], c2: [c3]}, stop_on_error=True, stop_undo_on_error=False, id_=1)

        res = cc1.invoke()

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertFalse(res)

        res = cc1.undo()

        self.assertEqual(2, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertTrue(res)

    def test_result(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)
        uc4 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=4)

        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, stop_on_error=True)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=ccu1, id_=5)
        c2 = Command(implementation=self.mocked_imp_error, var_context=self.mock_context, undo_command=ccu2,
                     undo_on_error=False, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []}, stop_on_error=True, stop_undo_on_error=False)

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END)}
                             , cc.result)

        self.assertEqual(1, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)
        self.assertEqual(False, res)

        res = cc.undo()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              6: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              1: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END)}
                             , cc.result)

        self.assertEqual(True, res)
        self.assertEqual(2, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)

    def test_composite_command_success(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=3)
        uc4 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=4)

        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3], uc3: [uc4]}, stop_on_error=True)

        c1 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=ccu1, id_=5)
        c2 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=ccu2, id_=6)

        cc = CompositeCommand({c1: [c2], c2: []}, stop_on_error=False, stop_undo_on_error=False)

        res = cc.invoke()

        self.assertDictEqual({5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END)}
                             , cc.result)
        self.assertEqual(True, res)
        self.assertEqual(2, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(0, self.mocked_imp_error.execute.call_count)

    def test_composite_command_error(self):
        uc1 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=1)
        uc2 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=2)
        uc3 = UndoCommand(implementation=self.mocked_imp_error, var_context=self.mock_context, id_=3)
        uc4 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=4)
        uc5 = UndoCommand(implementation=self.mocked_imp_succ, var_context=self.mock_context, id_=5)

        executor = ThreadPoolExecutor()
        ccu1 = CompositeCommand({uc1: []}, stop_on_error=True)
        ccu2 = CompositeCommand({uc2: [uc3, uc4]}, stop_on_error=True, executor=executor)

        c6 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=ccu1, id_=6)
        c7 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=ccu2, id_=7)
        c8 = Command(implementation=self.mocked_imp_succ, var_context=self.mock_context, undo_command=uc5, id_=8)

        cc = CompositeCommand({c6: [c7], c7: [c8]}, stop_on_error=False, stop_undo_on_error=False, executor=executor)

        res = cc.invoke()

        self.assertTrue(res)
        self.assertEqual(3, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(0, self.mocked_imp_error.execute.call_count)

        res = cc.undo()

        self.assertFalse(res)
        self.assertEqual(7, self.mocked_imp_succ.execute.call_count)
        self.assertEqual(1, self.mocked_imp_error.execute.call_count)

        self.assertDictEqual({1: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              2: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              3: CompletedProcess(success=False, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              4: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              5: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              6: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              7: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END),
                              8: CompletedProcess(success=True, stdout='stdout', stderr='stderr', rc=0,
                                                  start_time=START,
                                                  end_time=END)
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
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # @mock.patch('dimensigon.use_cases.deployment.create_operation', autospec=IOperationEncapsulation)
    def test_create_cmd_from_orchestration(self):
        at = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0001', name='create dir', version=1,
                            action_type=ActionType.SHELL, code='mkdir {{dir}}',
                            expected_stdout='',
                            expected_rc=0, system_kwargs={})

        o = Orchestration('Test Orchestration', 1, 'description', id='bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

        me = Server('me', port=5000, me=True, id='cccccccc-1234-5678-1234-cccccccc0001')
        remote = Server('remote', port=5000, id='cccccccc-1234-5678-1234-cccccccc0002')

        db.session.add_all([me, remote, o])

        s1 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0001', undo=False, action_template=at,
                        parents=[], target=['frontend'])
        s2 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0002', undo=True, action_template=at,
                        parents=[s1], stop_on_error=False, target=[])
        s3 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0003', undo=False, action_template=at,
                        parents=[s1], stop_on_error=False, stop_undo_on_error=False, target=['frontend'])
        s4 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0004', undo=True, action_template=at,
                        parents=[s3], target=[])
        s5 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0005', undo=True, action_template=at,
                        parents=[s4], stop_on_error=True, target=[])
        s6 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0006', undo=True, action_template=at,
                        parents=[s4, s5], target=[])
        s7 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0007', undo=False, action_template=at,
                        parents=[s3], undo_on_error=False, target=[])
        s8 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0008', undo=True, action_template=at,
                        parents=[s7], target=[])
        s9 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0009', undo=False, action_template=at,
                        children=[s2, s3], target=['backend'])

        cc = create_cmd_from_orchestration(o, Context({'dir': 'C:\\test_folder'}),
                                           hosts={'all': [me.id, remote.id], 'frontend': [me.id],
                                                  'backend': [remote.id]},
                                           executor=None, register=mock.Mock())

        c1, c9 = cc._dag.get_nodes_at_level(1)
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0001'), c1.id)
        self.assertIsInstance(c1, Command)
        self.assertTrue(c1.stop_on_error)
        self.assertTrue(c1.undo_on_error)
        self.assertIsNone(c1.stop_undo_on_error)

        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0002',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0009'), c9.id)
        self.assertIsInstance(c9, ProxyCommand)
        self.assertTrue(c9.stop_on_error)
        self.assertTrue(c9.undo_on_error)
        self.assertIsNone(c9.stop_undo_on_error)

        c21 = c1.undo_command
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0002'), c21.id)
        self.assertIsInstance(c21, UndoCommand)
        self.assertFalse(c21.stop_on_error)

        c22 = c9.undo_command
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0002',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0002'), c22.id)
        self.assertIsInstance(c22, ProxyUndoCommand)
        self.assertFalse(c22.stop_on_error)

        c3, = cc._dag.get_nodes_at_level(2)
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0003'), c3.id)
        self.assertIsInstance(c3, Command)
        self.assertFalse(c3.stop_on_error)
        self.assertTrue(c3.undo_on_error)
        self.assertFalse(c3.stop_undo_on_error)

        self.assertTupleEqual(('undo',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0003'), c3.undo_command.id)
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
        self.assertEqual('eeeeeeee-1234-5678-1234-eeeeeeee0007', cc7.id)
        self.assertIsInstance(cc7, CompositeCommand)
        self.assertFalse(cc7.stop_on_error)
        self.assertFalse(cc7.stop_undo_on_error)

        c71, c72 = cc7._dag.root
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0007'), c71.id)
        self.assertIsInstance(c71, Command)
        self.assertTrue(c71.stop_on_error)
        self.assertFalse(c71.undo_on_error)
        self.assertIsNone(c71.stop_undo_on_error)

        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0008'), c71.undo_command.id)
        self.assertIsInstance(c71.undo_command, UndoCommand)
        self.assertTrue(c71.undo_command.stop_on_error)

        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0002',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0007'), c72.id)
        self.assertIsInstance(c72, ProxyCommand)
        self.assertTrue(c72.stop_on_error)
        self.assertFalse(c72.undo_on_error)
        self.assertIsNone(c72.stop_undo_on_error)

        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0002',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0008'), c72.undo_command.id)
        self.assertIsInstance(c72.undo_command, ProxyUndoCommand)
        self.assertTrue(c72.undo_command.stop_on_error)

    def test_create_cmd_from_orchestration_one_step(self):
        at = ActionTemplate(id='aaaaaaaa-1234-5678-1234-aaaaaaaa0001', name='create dir', version=1,
                            action_type=ActionType.SHELL, code='mkdir {{dir}}',
                            expected_stdout='',
                            expected_rc=0, system_kwargs={})

        o = Orchestration('Test Orchestration', 1, 'description',
                          id='bbbbbbbb-1234-5678-1234-bbbbbbbb0001')

        me = Server('me', port=5000, me=True, id='cccccccc-1234-5678-1234-cccccccc0001')
        remote = Server('remote', port=5000, id='cccccccc-1234-5678-1234-cccccccc0002')

        db.session.add_all([me, remote, o])

        s1 = o.add_step(id='eeeeeeee-1234-5678-1234-eeeeeeee0001', undo=False, action_template=at,
                        parents=[], target=[])

        cc = create_cmd_from_orchestration(o, Context({'dir': './test_folder'}),
                                           hosts={'all': [me.id]},
                                           executor=None, register=mock.Mock())

        c1, = cc._dag.get_nodes_at_level(1)
        self.assertTupleEqual(('cccccccc-1234-5678-1234-cccccccc0001',
                               'eeeeeeee-1234-5678-1234-eeeeeeee0001'), c1.id)
        self.assertIsInstance(c1, Command)
        self.assertTrue(c1.stop_on_error)
        self.assertTrue(c1.undo_on_error)
        self.assertIsNone(c1.stop_undo_on_error)


class TestValidateInputChain(base.OneNodeMixin, TestCase):

    def test_validate_input_chain(self):
        o = Orchestration("test", 1)
        s1 = o.add_step(undo=False, schema={'input': {'param1': {}},
                                            'required': ['param1'],
                                            'output': {'param2': {}}}, action_type=ActionType.SHELL, code='')
        s2 = o.add_step(undo=False, parents=[s1], schema={'input': {'param3': {}, 'param4': {}},
                                                          'required': ['param3', 'param4'],
                                                          'mapping': {'param3': {'from': 'param2'}}},
                        action_type=ActionType.SHELL, code='')
        s3 = o.add_step(undo=False, parents=[s2], schema={'input': {'param2': {},
                                                                    'param5': {}},
                                                          'required': ['param2']},
                        action_type=ActionType.SHELL, code='')

        validate_input_chain(o, params=dict(input={'param1', 'param4'}))

        with self.assertRaises(errors.MissingParameters) as e:
            validate_input_chain(o, params=dict(input={'param1'}))

        self.assertEqual(['input.param4'], e.exception.parameters)

    def test_validate_input_chain_mapping_constant_value(self):
        o = Orchestration("test", 1)
        s1 = o.add_step(undo=False, schema={'input': {'param1': {}},
                                            'required': {'param1'},
                                            'output': {'param2': {}}}, action_type=ActionType.SHELL, code='')
        s2 = o.add_step(undo=False, parents=[s1], schema={'input': {'param3': {}, 'param4': {}},
                                                          'required': ['param3', 'param4'],
                                                          'mapping': {'param3': "value"}},
                        action_type=ActionType.SHELL, code='')
        s3 = o.add_step(undo=False, parents=[s2], schema={'input': {'param5': {}},
                                                          'required': ['param5']},
                        action_type=ActionType.SHELL, code='')

        with self.assertRaises(errors.MissingParameters) as e:
            validate_input_chain(o, params=dict(input={'param1', 'param4'}))

        self.assertEqual(['input.param5'], e.exception.parameters)

    def test_validate_input_chain_mapping_action_template(self):
        o = Orchestration("test", 1)
        at = ActionTemplate("action", 1, action_type=ActionType.SHELL, code='', schema={'input': {'param1': {}},
                                                                                        'required': ['param1']})

        s1 = o.add_step(undo=False, action_template=at, schema={'mapping': {'param1': "value"}})
        s2 = o.add_step(undo=False, action_type=ActionType.SHELL, schema={'input': {'param2': {}},
                                                                          'required': ['param2']})

        validate_input_chain(o, params=dict(input={'param2'}))

        with self.assertRaises(errors.MissingParameters) as e:
            validate_input_chain(o, params=dict(input={'param1'}))

        self.assertEqual(['input.param2'], e.exception.parameters)

    def test_validate_input_chain_mapping_with_orch(self):
        o = Orchestration('Schema Orch', 1, id='00000000-0000-0000-0000-000000000001')
        s1 = o.add_step(id=1, action_type=ActionType.SHELL, undo=False,
                        schema={'input': {'1_a': {},
                                          '1_b': {}},
                                'required': ['1_b'],
                                'output': ['1_c']})
        s2 = o.add_step(undo=False, action_type=ActionType.SHELL,
                        schema={'input': {'2_a': {}},
                                'required': ['2_a'],
                                'output': ['2_b']})

        s3 = o.add_step(undo=False, action_type=ActionType.SHELL, parents=[s1],
                        schema={'input': {'3_a': {},
                                          '3_b': {}},
                                'required': ['3_a'],
                                'mapping': {'3_a': {'from': '2_b'}}})

        db.session.add(o)
        o2 = Orchestration('Schema Orch', 1)
        at = ActionTemplate.query.filter_by(name='orchestration', version=1).one()
        s1 = o2.add_step(id=1, action_template=at,
                         undo=False,
                         schema={'mapping': {'orchestration': o.id}})
        s2 = o2.add_step(undo=False, action_type=1, parents=[s1],
                         schema={'input': {"1": {},
                                           "2": {}},
                                 'required': ["1"],
                                 'mapping': {"1": {'from': '1_c'}}})

        validate_input_chain(o2, params=dict(input={'hosts', '1_b', '2_a'}))

    def test_validate_input_chain_mapping_default_value(self):
        o = Orchestration("test", 1)
        at1 = ActionTemplate("action1", 1, action_type=ActionType.SHELL, code='', schema={'input': {'input1': {},
                                                                                                    'input2': {
                                                                                                        'default': 1}},
                                                                                          'required': ['input1'],
                                                                                          'output': ['out1', 'out2']})
        at2 = ActionTemplate("action2", 1, action_type=ActionType.SHELL, code='', schema={'input': {'out1': {},
                                                                                                    'out2': {},
                                                                                                    'input2': {}},
                                                                                          'required': ['out1', 'out2',
                                                                                                       'input2'],
                                                                                          'output': []})

        s1 = o.add_step(undo=False, action_template=at1, schema={})
        s2 = o.add_step(undo=False, action_template=at2, schema={}, parents=[s1])

        with self.assertRaises(errors.MissingParameters) as e:
            validate_input_chain(o, params=dict(input={'input1'}))

        self.assertEqual(['input.input2'], e.exception.parameters)

    def test_validate_input_chain_vault_container(self):
        o = Orchestration("test", 1)
        at1 = ActionTemplate("action1", 1, action_type=ActionType.SHELL, code='', schema={'input': {'vault.var': {}},
                                                                                          'required': ['vault.var']})

        s1 = o.add_step(undo=False, action_template=at1, schema={})

        validate_input_chain(o, params=dict(vault={'var'}))

        with self.assertRaises(errors.MissingParameters) as e:
            validate_input_chain(o, params=dict())

        self.assertEqual(['vault.var'], e.exception.parameters)


class TestImplementationCommand(TestCase):

    def set_mocks(self, start=START, end=END):
        self.mocked_imp_succ = mock.Mock()
        self.mocked_imp_error = mock.Mock()

        self.mocked_imp_succ.execute.return_value = CompletedProcess(success=True, stdout='stdout', stderr='stderr',
                                                                     rc=0,
                                                                     start_time=start,
                                                                     end_time=end)

        self.mocked_imp_error.execute.return_value = CompletedProcess(success=False, stdout='stdout', stderr='stderr',
                                                                      rc=0,
                                                                      start_time=start,
                                                                      end_time=end)

    def setUp(self) -> None:
        self.set_mocks()

    def test_create_step_execution(self):
        mock_register = mock.Mock()
        mock_register.create_step_execution.return_value = 1
        mock_context = mock.Mock()

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context, register=mock_register)

        ic.create_step_execution()

        mock_register.create_step_execution.assert_called_once()
        # set step_execution_id into the environment context
        mock_context.env.update.assert_called_once_with(step_execution_id=1)
        self.assertEqual(1, ic.step_execution_id)

    def test_register_execution(self):
        mock_register = mock.Mock()
        mock_context = mock.Mock()

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context, register=mock_register)
        ic.params = {}
        ic._elapsed_times = {'pre_process': 1}

        ic.register_execution()

        mock_register.save_step_execution.assert_called_once_with(ic, params=ic.params, pre_process=1)

    def test_pre_process(self):
        mock_context = mock.Mock()

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context,
                         pre_process="vc.set('foo', 'bar')")
        ic.pre_process()
        mock_context.set.assert_called_once_with('foo', 'bar')

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context,
                         pre_process="raise KeyError('foo')")
        ic.pre_process()
        self.assertFalse(ic._cp.success)
        self.assertIn("KeyError: 'foo'", ic._cp.stderr)

    def test_extract_params(self):
        c = Context({'string': "abc", "integer": 1}, {}, {'server_id': 4})

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=c,
                         pre_process="vc.set('foo', 'bar')", signature={"input": {"string": {"type": "string"},
                                                                                  "optional": {"type": "string"},
                                                                                  "default": {"type": "string",
                                                                                              "default": "def"}},
                                                                        })
        ic.extract_params()

        self.assertDictEqual({'input': {'string': "abc", "default": "def"}},
                             ic.params)

        # required
        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=c,
                         pre_process="vc.set('foo', 'bar')", signature={"input": {"bar": {"type": "string"},
                                                                                  },
                                                                        "required": ["bar"]})
        ic.extract_params()

        self.assertFalse(ic._cp.success)
        self.assertEqual(str(errors.MissingParameters(['input.bar'])), ic._cp.stderr)

        # validation error
        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=c,
                         pre_process="vc.set('foo', 'bar')", signature={"input": {"string": {"type": "integer"},
                                                                                  }})
        ic.extract_params()

        self.assertFalse(ic._cp.success)
        self.assertTrue(ic._cp.stderr.startswith('Param validation error:'))

    def test_post_process(self):
        mock_context = mock.Mock()

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context,
                         post_process="vc.set('foo', 'bar')")
        ic.post_process()
        mock_context.set.assert_called_once_with('foo', 'bar')

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=mock_context,
                         post_process="raise KeyError('foo')")
        ic._cp = CompletedProcess()

        ic.post_process()
        self.assertFalse(ic._cp.success)
        self.assertIn("KeyError: 'foo'", ic._cp.stderr)

    def test_check_output_variables(self):
        context = {}

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=context,
                         signature={'output': ['output', 'value']})
        ic._cp = CompletedProcess(True)

        ic.check_output_variables()

        self.assertFalse(ic._cp.success)
        self.assertEqual(f"Missing output values: output, value", ic._cp.stderr)

        ic = UndoCommand(implementation=self.mocked_imp_succ, var_context=context,
                         signature={"input": {}})
        ic._cp = CompletedProcess(True)

        ic.check_output_variables()

        self.assertTrue(ic._cp.success)
