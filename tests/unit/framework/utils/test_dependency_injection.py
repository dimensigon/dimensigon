from unittest import mock, TestCase

from dm.framework.domain import Id
from dm.framework.exceptions import DefinitionNotFound, AmbiguousDefinition, NoIdentifierSpecified, NoContainerProvided, \
    GlobalContainerNotSet
from dm.framework.utils.collection import frozendict

from dm.framework.utils.dependency_injection import (
    Component,
    Container,
    container_supplier,
    inject,
    Inject,
    scope,
    Scopes, set_global_container)


class WheelInterface:
    name: str


class FrameInterface:
    name: str


@scope(Scopes.INSTANCE)
class RoadFrame(FrameInterface, Component):
    name = 'Road frame'


class GravelFrame(FrameInterface, Component):
    name = 'Gravel frame'


class CustomColoredFrame(FrameInterface, Component):
    def __init__(self, container, color):
        self.color = color
        super().__init__(container)

    @property
    def name(self):
        return f'Custom {self.color} frame'


class RoadWheel(WheelInterface, Component):
    name = 'Road wheel'


class GravelWheel(WheelInterface, Component):
    name = 'Gravel wheel'


class CustomColoredWheel(WheelInterface, Component):
    def __init__(self, container, color):
        self.color = color
        super().__init__(container)

    @property
    def name(self):
        return f'Custom {self.color} wheel'


class Bike:
    def __init__(self, container: Container):
        """
        Doesn't inherit Component features. Manually uses DI container as a dependency manager and
        sets injected instances to the Bike instance fields.
        """
        self.frame = container.find_by_name('frame')
        self.wheel = container.find_by_interface(WheelInterface)

    @property
    def components(self):
        return {
            'frame': self.frame.name,
            'wheel': self.wheel.name,
        }


class Trike(Component):
    """
    Inherits Component features. Automatically is being injected with DI instances using Inject
    descriptor.
    """
    front_wheel: WheelInterface = Inject()
    left_wheel = Inject(interface=WheelInterface)
    right_wheel = Inject(name='right')
    frame: FrameInterface = Inject(name='frame')

    @property
    def components(self):
        return {
            'front': self.front_wheel.name,
            'left': self.left_wheel.name,
            'right': self.right_wheel.name,
            'frame': self.frame.name,
        }


class TestContainer(TestCase):

    def setUp(self) -> None:
        self.container = Container(default_scope=Scopes.INSTANCE)

    def test_container_registration(self):
        self.container.register_by_name(name='frame', constructor=RoadFrame)
        self.container.register_by_interface(interface=WheelInterface, constructor=RoadWheel)
        self.assertDictEqual(Bike(self.container).components, {
            'frame': 'Road frame',
            'wheel': 'Road wheel',
        })

    def test_container_interface_duplicates(self):
        interface = FrameInterface
        self.container.register_by_interface(interface, RoadFrame)
        # registering again the same signature results with an error
        with self.assertRaises(AmbiguousDefinition) as error_info:
            self.container.register_by_interface(interface, GravelFrame)
        assert error_info.exception.args == (interface, None)
        # but registering with the same interface and different qualifier is a different signature
        # and ends with a success
        self.container.register_by_interface(interface, GravelFrame, qualifier='gravel')

    def test_container_interface_not_found(self):
        interface = FrameInterface
        qualifier = 'qualifier'
        with self.assertRaises(DefinitionNotFound) as error_info:
            self.container.find_by_interface(interface, qualifier)
        assert error_info.exception.args == (interface, qualifier)

    def test_container_name_duplicates(self):
        name = 'frame'
        self.container.register_by_name(name=name, constructor=RoadFrame)
        # registering again the same signature results with an error
        with self.assertRaises(AmbiguousDefinition) as error_info:
            self.container.register_by_name(name=name, constructor=GravelFrame)
        assert error_info.exception.args == (name, None)
        # but registering with the same interface and different qualifier is a different signature
        # and ends with a success
        self.container.register_by_name(name=name, constructor=GravelFrame, qualifier='gravel')

    def test_container_name_not_found(self):
        name = 'frame'
        qualifier = 'qualifier'
        with self.assertRaises(DefinitionNotFound) as error_info:
            self.container.find_by_name(name, qualifier)
        assert error_info.exception.args == (name, qualifier)

    def test_constructor_kwargs(self):
        self.container.register_by_name(
            name='frame',
            constructor=CustomColoredFrame,
            kwargs={'color': 'pink'}
        )
        self.container.register_by_interface(
            interface=WheelInterface,
            constructor=CustomColoredWheel,
            kwargs={'color': 'pink'}
        )
        assert Bike(self.container).components == {
            'frame': 'Custom pink frame',
            'wheel': 'Custom pink wheel'
        }


class TestScopes(TestCase):

    def setUp(self) -> None:
        self.container = Container()

    def test_scope_class(self):
        assert repr(Scopes.INSTANCE) == f'<Scopes.{Scopes.INSTANCE.name}>'
        assert Scopes.INSTANCE(self.container, RoadWheel, {}).name == 'Road wheel'

    def test_scope_decorator(self):
        @scope(Scopes.SINGLETON)
        class MyFrame(FrameInterface, Component):
            name = 'My frame'

        self.container.register_by_name(name='frame', constructor=MyFrame)
        instance_1 = self.container.find_by_name('frame')
        instance_2 = self.container.find_by_name('frame')
        assert MyFrame.__di_scope_type__ is Scopes.SINGLETON
        assert instance_1 is instance_2

    def test_singleton_scope(self):
        self.container.register_by_name(name='frame', constructor=RoadFrame, scope=Scopes.SINGLETON)
        instance_1 = self.container.find_by_name('frame')
        instance_2 = self.container.find_by_name('frame')
        assert instance_1 is instance_2

    def test_singleton_scope_same_constructor(self):
        self.container.register_by_name(name='frame', constructor=RoadFrame, scope=Scopes.SINGLETON, qualifier="Frame1")
        self.container.register_by_name(name='frame', constructor=RoadFrame, scope=Scopes.SINGLETON, qualifier="Frame2")
        instance_1 = self.container.find_by_name('frame', "Frame1")
        instance_2 = self.container.find_by_name('frame', "Frame1")
        instance_3 = self.container.find_by_name('frame', "Frame2")
        self.assertTrue(instance_1 is instance_2)
        self.assertFalse(instance_1 is instance_3)


class TestInjectDescriptor(TestCase):

    def setUp(self) -> None:
        self.container = Container(default_scope=Scopes.INSTANCE)
        self.container.register_by_interface(FrameInterface, RoadFrame)
        self.container.register_by_interface(WheelInterface, RoadWheel)
        self.container.register_by_name('frame', GravelFrame)
        self.container.register_by_name('wheels', RoadWheel)
        self.container.register_by_name('right', GravelWheel)

    def test_descriptor_injection(self):
        trike = Trike(self.container)
        assert trike.components == {
            'front': 'Road wheel',
            'left': 'Road wheel',
            'right': 'Gravel wheel',
            'frame': 'Gravel frame',
        }

    def test_get_class(self):
        class Bike(Component):
            wheel: WheelInterface = Inject()

        assert isinstance(Bike.wheel, Inject)

    def test_no_name_no_interface(self):
        class NoAnnotationBike(Component):
            wheel = Inject()

        with self.assertRaises(NoIdentifierSpecified) as error_info:
            assert NoAnnotationBike(self.container).wheel

    def test_dunder_dependencies(self):
        trike = Trike(self.container)
        assert isinstance(trike.__dependencies__, frozendict)
        assert trike.__dependencies__ == {
            'front_wheel': Trike.front_wheel,
            'left_wheel': Trike.left_wheel,
            'right_wheel': Trike.right_wheel,
            'frame': Trike.frame,
        }


class TestInjectDecorator(TestCase):
    class Bike(Component):

        @inject
        def compose_success(self, frame: FrameInterface = Inject(), front_wheel=Inject(name='front'),
                            rear_wheel=Inject(interface=WheelInterface)):
            return {
                'frame': frame.name,
                'front': front_wheel.name,
                'rear': rear_wheel.name
            }

        @inject
        def compose_no_identifier(self, frame=Inject()):
            pass

    class BikeGlobal:

        @inject
        def compose_success(self, frame: FrameInterface = Inject(), front_wheel=Inject(name='front'),
                            rear_wheel=Inject(interface=WheelInterface)):
            return {
                'frame': frame.name,
                'front': front_wheel.name,
                'rear': rear_wheel.name
            }

        @inject
        def compose_no_identifier(self, frame=Inject()):
            pass

    def setUp(self) -> None:
        self.container = Container(default_scope=Scopes.INSTANCE)
        self.container.register_by_interface(FrameInterface, RoadFrame)
        self.container.register_by_interface(WheelInterface, RoadWheel)
        self.container.register_by_name('front', GravelWheel)
        self.instance = self.Bike(self.container)

    def test_inject(self):
        assert self.Bike(self.container).compose_success() == {
            'frame': 'Road frame',
            'front': 'Gravel wheel',
            'rear': 'Road wheel',
        }

    def test_inject_args(self):
        with self.assertRaises(TypeError) as error_info:
            self.instance.compose_success(GravelFrame(self.container))
        assert error_info.exception.args == ("compose_success() got multiple values for argument 'frame'",)

    def test_inject_kwargs(self):
        assert self.instance.compose_success(frame=GravelFrame(self.container)) == {
            'frame': 'Gravel frame',
            'front': 'Gravel wheel',
            'rear': 'Road wheel',
        }

    def test_inject_no_name_or_interface(self):
        with self.assertRaises(NoIdentifierSpecified) as error_info:
            self.instance.compose_no_identifier()

    def test_inject_no_container(self):
        # noinspection PyTypeChecker
        instance = self.Bike(None)
        with self.assertRaises(NoContainerProvided) as error_info:
            assert instance.compose_success()

    def test_injectable_function(self):
        mock_dependency = mock.Mock()

        @container_supplier
        @inject
        def func(dependency=Inject(name="dependency"), **kwargs):
            dependency(**kwargs)
            return 42

        self.container.register_by_name("dependency", lambda *args: mock_dependency)
        f_closure = func(self.container)
        result = f_closure(foo='bar')

        mock_dependency.assert_called_once_with(foo='bar')
        assert result == 42


class TestGlobalInject(TestCase):
    def test_global_injection(self):
        import dm.framework.utils.dependency_injection as di

        di.g_container = None

        class Foo:
            id_ = Id(factory=Inject(name="Seq", global_container=True))

            @property
            def id(self):
                return self.id_

        f1 = Foo()
        f2 = Foo()

        with self.assertRaises(GlobalContainerNotSet):
            assert f1.id

        seq = (x for x in range(5, 10))
        container = set_global_container()
        container.register_by_name(name="Seq", constructor=lambda: next(seq), scope=Scopes.INSTANCE_NO_CONTAINER)

        self.assertEqual(5, f1.id)
        self.assertEqual(6, f2.id)
