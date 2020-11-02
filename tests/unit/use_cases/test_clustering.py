from unittest import TestCase

from dimensigon.use_cases.clustering import EventDispatcher, AliveEvent, DeathEvent, ClusterManager

event_id = None


def alive_count(event):
    global event_id
    event_id = event.ident


class TestEventDispatcher(TestCase):

    def test_event(self):
        ed = EventDispatcher()

        ed.listen(AliveEvent, alive_count)

        ed(DeathEvent(1))

        self.assertIsNone(event_id)

        a = AliveEvent(2)
        ed(a)

        self.assertEqual(2, event_id)
