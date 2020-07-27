import threading
from unittest import TestCase

from dimensigon.utils.talkback import Talkback


class TestTalkback(TestCase):

    def test_wait(self):
        t = Talkback()

        th = threading.Timer(0.001, t.update, kwargs=dict(key=1))
        th.start()
        self.assertTrue(t.wait_exists('key', timeout=10))
        self.assertEqual(0, len(t._listeners))
        self.assertDictEqual({'key': 1}, t)

        self.assertTrue(t.wait_exists('key', timeout=0.01))
        self.assertEqual(0, len(t._listeners))

        th = threading.Timer(0.001, t.update, args=((('a', 2),),))
        th.start()
        self.assertTrue(t.wait_exists('a', timeout=10))
        self.assertEqual(0, len(t._listeners))
        self.assertIn('a', t)

        th = threading.Timer(0.001, t.update, args=({'key': 3},))
        th.start()
        self.assertTrue(t.wait_update('key', timeout=10))
        self.assertEqual(0, len(t._listeners))
        self.assertDictEqual({'key': 3, 'a': 2}, t)

        self.assertFalse(t.wait_exists('none', timeout=0.01))
