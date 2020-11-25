from unittest import TestCase
from unittest.mock import patch, Mock

from dimensigon.utils.event_handler import EventHandler, _RegistryContainer, Event


class TestEventHandler(TestCase):

    def setUp(self) -> None:
        self.eh = EventHandler()

    @patch('dimensigon.utils.event_handler.time.time')
    def test_discard(self, mock_time):
        mock_time.return_value = 2
        self.eh.discard_after = 2
        self.eh._registry[1] = _RegistryContainer(lambda x: x, (), {}, 1)
        self.eh._registry[2] = _RegistryContainer(lambda x: x, (), {}, 0)
        self.eh._pending_events[1] = (Event(1, data={}), 1)
        self.eh._pending_events[2] = (Event(2, data={}), 0)

        self.eh.discard()

        self.assertEqual(1, len(self.eh._registry))
        self.assertEqual(1, len(self.eh._pending_events))
        self.assertIn(1, self.eh._registry)
        self.assertIn(1, self.eh._pending_events)

    @patch('dimensigon.utils.event_handler.time.time')
    def test_register(self, mock_time):
        func = Mock()
        mock_time.return_value = 0
        self.eh.discard_after = 2
        self.eh.register(1, func)
        self.assertEqual(1, len(self.eh._registry))

        with self.assertRaises(ValueError):
            self.eh.register(1, func)

        e = Event(2, {})
        self.eh._pending_events[2] = (e, 3)
        mock_time.return_value = 3
        func2 = Mock()
        self.eh.register(2, func2, ('arg',), kwargs={'param': 'kwarg'})

        func2.assert_called_once_with(e, 'arg', param='kwarg')
        self.assertEqual(0, len(self.eh._registry))

    @patch('dimensigon.utils.event_handler.time.time')
    def test_dispatch(self, mock_time):
        func = Mock()
        mock_time.return_value = 0
        self.eh.discard_after = 2
        self.eh.register(1, func)
        e = Event(1, {})
        self.eh.dispatch(e)
        func.assert_called_once_with(e)

        e = Event(2, {})
        self.eh.dispatch(e)
        self.assertIn(2, self.eh._pending_events)

        mock_time.return_value = 2
        e = Event(3, {})
        self.eh.dispatch(e)
        self.assertNotIn(2, self.eh._pending_events)
        self.assertIn(3, self.eh._pending_events)
