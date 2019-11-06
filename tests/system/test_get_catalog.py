import datetime
import uuid
from itertools import count
from unittest import TestCase, mock

from dm.domain.catalog_manager import CatalogManager
from dm.domain.entities import ActionTemplate, ActionType, Step, Orchestration
from dm.domain.schemas import set_container
from dm.framework.data.dao import InMemoryDao
from dm.framework.exceptions import IdAlreadyExists
from dm.framework.interfaces.dao import IDao
from dm.framework.utils.dependency_injection import Container, Scopes as ContainerScope, Scopes, set_global_container
from dm.repositories import ActionTemplateRepo, StepRepo, OrchestrationRepo


class TestActionRepo(TestCase):

    def setUp(self) -> None:
        self.dao_container = Container(default_scope=ContainerScope.SINGLETON). \
            register_by_interface(interface=IDao, constructor=InMemoryDao, qualifier=ActionTemplate). \
            register_by_interface(interface=CatalogManager, constructor=CatalogManager,
                                  scope=ContainerScope.SINGLETON_NO_CONTAINER,
                                  kwargs={'type_': datetime.datetime})

        self.action_template_dao = self.dao_container.find_by_interface(interface=IDao, qualifier=ActionTemplate)
        self.action_repo = ActionTemplateRepo(self.dao_container)

    @mock.patch('dm.domain.catalog_manager.get_now')
    def test_add_action_template(self, mocked_now):
        self.maxDiff = None
        ActionTemplate.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('11111111-2222-3333-4444-11111111aaa1'),
                                                                    uuid.UUID('11111111-2222-3333-4444-11111111aaa2'),
                                                                    uuid.UUID('11111111-2222-3333-4444-11111111aaa3'),
                                                                    uuid.UUID('11111111-2222-3333-4444-11111111aaa4')])
        mocked_now.return_value = datetime.datetime(2019, 9, 17, 13, 30, 12, 0)

        action_template = ActionTemplate(name='test', version=1, action_type=ActionType.NATIVE, code="dir",
                                         data_mark=datetime.datetime(year=2019, month=1, day=1, hour=0, minute=5,
                                                                     second=30,
                                                                     microsecond=100000))
        self.action_repo.add(action_template)

        self.assertDictEqual(self.action_template_dao._register,
                             {'11111111-2222-3333-4444-11111111aaa1': dict(id='11111111-2222-3333-4444-11111111aaa1',
                                                                           name='test', version=1,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190101000530100000')})
        self.action_repo.add(
            ActionTemplate(name='test', version=2, action_type=ActionType.NATIVE, code="dir"))

        self.assertDictEqual(self.action_template_dao._register,
                             {'11111111-2222-3333-4444-11111111aaa1': dict(id='11111111-2222-3333-4444-11111111aaa1',
                                                                           name='test', version=1,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190101000530100000'),
                              '11111111-2222-3333-4444-11111111aaa2': dict(id='11111111-2222-3333-4444-11111111aaa2',
                                                                           name='test', version=2,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190917133012000000'),
                              })
        self.action_repo.add(
            ActionTemplate(name='test2', version=1, action_type=ActionType.NATIVE, code="dir"))

        self.assertDictEqual(self.action_template_dao._register,
                             {'11111111-2222-3333-4444-11111111aaa1': dict(id='11111111-2222-3333-4444-11111111aaa1',
                                                                           name='test', version=1,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190101000530100000'),
                              '11111111-2222-3333-4444-11111111aaa2': dict(id='11111111-2222-3333-4444-11111111aaa2',
                                                                           name='test', version=2,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190917133012000000'),
                              '11111111-2222-3333-4444-11111111aaa3': dict(id='11111111-2222-3333-4444-11111111aaa3',
                                                                           name='test2', version=1,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190917133012000000'),
                              })

        with self.assertRaises(IdAlreadyExists):
            self.action_repo.add(
                ActionTemplate(id='11111111-2222-3333-4444-11111111aaa3', name='test2', version=1,
                               action_type=ActionType.NATIVE, code="code test"))

        mocked_now.return_value = datetime.datetime(2019, 9, 17, 13, 30, 13, 0)
        self.action_repo.update(
            ActionTemplate(id='11111111-2222-3333-4444-11111111aaa3',
                           name='test2', version=1,
                           action_type=ActionType.NATIVE, code='code test',
                           parameters={}, expected_output=None,
                           expected_rc=None, system_kwargs={},
                           data_mark='20190917133012000000'))

        self.assertDictEqual(self.action_template_dao._register,
                             {'11111111-2222-3333-4444-11111111aaa1': dict(id='11111111-2222-3333-4444-11111111aaa1',
                                                                           name='test', version=1,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190101000530100000'),
                              '11111111-2222-3333-4444-11111111aaa2': dict(id='11111111-2222-3333-4444-11111111aaa2',
                                                                           name='test', version=2,
                                                                           action_type='NATIVE', code='dir',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190917133012000000'),
                              '11111111-2222-3333-4444-11111111aaa3': dict(id='11111111-2222-3333-4444-11111111aaa3',
                                                                           name='test2', version=1,
                                                                           action_type='NATIVE', code='code test',
                                                                           parameters={}, expected_output=None,
                                                                           expected_rc=None, system_kwargs={},
                                                                           data_mark='20190917133013000000'),
                              })

    def test_find_action_template(self):
        ActionTemplate.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('11111111-2222-3333-4444-11111111aaa1')])
        at1 = ActionTemplate(name='test', version=1, action_type=ActionType.NATIVE, code="dir")
        self.action_repo.add(at1)
        at2 = self.action_repo.find('11111111-2222-3333-4444-11111111aaa1')
        self.assertEqual(at1, at2)
        self.assertDictEqual(at1.__dict__, at2.__dict__)
        self.assertFalse(at1 is at2)


class TestOrchestrationRepo(TestCase):

    def setUp(self) -> None:
        self.dao_container = Container(default_scope=ContainerScope.SINGLETON). \
            register_by_interface(interface=IDao, constructor=InMemoryDao, qualifier=ActionTemplate). \
            register_by_interface(interface=IDao, constructor=InMemoryDao, qualifier=Step). \
            register_by_interface(interface=IDao, constructor=InMemoryDao, qualifier=Orchestration). \
            register_by_interface(interface=CatalogManager, constructor=CatalogManager,
                                  scope=ContainerScope.SINGLETON_NO_CONTAINER,
                                  kwargs={'type_': datetime.datetime})

        self.action_template_dao = self.dao_container.find_by_interface(interface=IDao, qualifier=ActionTemplate)
        self.action_repo = ActionTemplateRepo(self.dao_container)

        self.step_dao = self.dao_container.find_by_interface(interface=IDao, qualifier=Step)
        self.step_repo = StepRepo(self.dao_container)

        self.orchestration_dao = self.dao_container.find_by_interface(interface=IDao, qualifier=Orchestration)
        self.orchestration_repo = OrchestrationRepo(self.dao_container)
        set_container(self.dao_container)

    def test_save_orchestration(self):
        ActionTemplate.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('11111111-2222-3333-4444-11111111aaa1'),
                                                                    uuid.UUID('11111111-2222-3333-4444-11111111aaa2')])
        Step.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('aaaaaaaa-2222-3333-4444-11111111aaa1'),
                                                          uuid.UUID('aaaaaaaa-2222-3333-4444-11111111aaa2'),
                                                          uuid.UUID('aaaaaaaa-2222-3333-4444-11111111aaa3')])
        Orchestration.__id__.factory = mock.MagicMock(side_effect=[uuid.UUID('bbbbbbbb-2222-3333-4444-11111111aaa1'),
                                                                   uuid.UUID('bbbbbbbb-2222-3333-4444-11111111aaa2'),
                                                                   uuid.UUID('bbbbbbbb-2222-3333-4444-11111111aaa3')])

        class Seq:
            c = count(1)

            def next_(self) -> int:
                return next(self.c)

        c = Container(default_scope=Scopes.INSTANCE_NO_CONTAINER)
        set_global_container(c)
        c.register_by_name(name="StepSequence", constructor=Seq().next_)

        # Step.set_sequence(Seq().next_)
        at1 = ActionTemplate(name='test', version=1, action_type=ActionType.NATIVE, code="dir")
        at2 = ActionTemplate(name='test2', version=1, action_type=ActionType.NATIVE, code="test code 2")
        self.action_repo.add(at1)
        self.action_repo.add(at2)
        o1 = Orchestration('orchestration1', version=1)
        s11 = o1.add_step(undo=True, action_template=at1)
        s12 = o1.add_step(undo=True, action_template=at2, parents=[s11])

        self.step_repo.add(s11)
        self.step_repo.add(s12)

        o2 = Orchestration('orchestration1', version=2)
        s22 = o2.add_step(undo=True, action_template=at2, parents=[])
        self.step_repo.add(s22)

        self.orchestration_repo.add(o1)
        self.orchestration_repo.add(o2)

        o = self.orchestration_repo.find(id_='bbbbbbbb-2222-3333-4444-11111111aaa1')
        o.description = 'another description'
        o3 = self.orchestration_repo.find(id_='bbbbbbbb-2222-3333-4444-11111111aaa1')

        self.assertEqual(o1, o)

        self.assertTrue(o.eq_imp(o1))

        self.assertNotEqual(o.description, o3.description)

        self.assertEqual(o, o3)

        self.assertTrue(o.eq_imp(o3))
