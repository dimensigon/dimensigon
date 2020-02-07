import time
from unittest import TestCase

from dm.web.extensions.job_background import AsyncOperator, TaskStatus


class TestAsyncOperator(TestCase):

    @staticmethod
    def async_op(d):
        d['async_op'] += 1
        return 2

    @staticmethod
    def callback1(d, data):
        d['callback'] += data.returndata

    def tearDown(self) -> None:
        try:
            self.first_done.set()
        except:
            pass
        try:
            self.second_done.set()
        except:
            pass
        self.ao.wait_tasks(timeout=3)
        try:
            self.ao.stop()
        except:
            pass

    def test_register_and_run(self):
        dict_test = dict()
        dict_test['async_op'] = 0
        dict_test['callback'] = 0

        self.ao = AsyncOperator(priority=False)

        self.ao.register(async_proc=self.async_op, async_proc_args=(dict_test,),
                         callback=TestAsyncOperator.callback1, callback_args=(dict_test,))
        self.ao.register(async_proc=self.async_op, async_proc_args=(dict_test,),
                         callback=TestAsyncOperator.callback1, callback_args=(dict_test,))

        self.ao.start()

        while not self.ao.done:
            pass

        self.assertDictEqual(dict_test, {'async_op': 2, 'callback': 4})

    def test_register_and_run_with_priority(self):
        mailbox = list()

        self.ao = AsyncOperator(priority=True)

        self.ao.register(lambda x: x.append('Mail with priority 100'), (mailbox,), priority=10)
        self.ao.register(lambda x: x.append('Mail with priority 1'), (mailbox,), priority=1)

        self.ao.start()

        self.ao.wait_tasks()

        self.assertListEqual(mailbox, ['Mail with priority 1', 'Mail with priority 100'])

    def test_wait_tasks(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1():
            self.first_done.wait()
            return 'First Done'

        def process2():
            self.second_done.wait()
            return 'Second Done'

        result = []

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1, callback=lambda data: result.append(data.returndata))
        id2 = self.ao.register(process2, callback=lambda data: result.append(data.returndata))

        self.ao.start()

        start = time.time()
        self.assertFalse(self.ao.wait_tasks(timeout=0.05))
        end = time.time()

        self.assertGreaterEqual(end - start, 0.05)

        self.assertFalse(self.ao.wait_tasks(id1, timeout=0.01))
        self.assertFalse(self.ao.wait_tasks(id2, timeout=0.01))
        self.assertFalse(self.ao.wait_tasks([id1, id2], timeout=0.01))
        self.assertListEqual(result, [])

        self.first_done.set()

        self.assertTrue(self.ao.wait_tasks(id1))
        self.assertFalse(self.ao.wait_tasks(id2, timeout=0.01))
        self.assertFalse(self.ao.wait_tasks([id1, id2], timeout=0.01))
        self.assertListEqual(result, ['First Done'])

        self.second_done.set()

        self.assertTrue(self.ao.wait_tasks(id2))
        self.assertTrue(self.ao.wait_tasks([id1, id2]))
        self.assertTrue(self.ao.wait_tasks())
        self.assertListEqual(result, ['First Done', 'Second Done'])

    def test_progress(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        self.first_p_done = threading.Event()
        self.second_p_done = threading.Event()

        def process1(set_progress):
            set_progress(0)
            self.first_done.wait()
            set_progress(50)
            self.first_p_done.set()
            self.second_done.wait()
            set_progress(100)
            self.second_p_done.set()
            return 'First Done'

        def process2(set_progress):
            set_progress(50)
            return 'Second Done'

        result = []

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1, callback=lambda data: result.append(data.returndata), fail_silently=False)

        self.ao.start()

        self.assertEqual(self.ao.progress(id1), 0)

        self.first_done.set()
        self.first_p_done.wait()
        self.assertEqual(self.ao.progress(id1), 50)

        self.second_done.set()
        self.second_p_done.wait()
        self.assertEqual(self.ao.progress(id1), 100)
        self.ao.wait_tasks(id1)
        self.assertListEqual(result, ['First Done'])

        id2 = self.ao.register(process2, callback=lambda data: result.append(data.returndata), fail_silently=False)
        self.ao.wait_tasks()
        self.assertListEqual(self.ao.progress([id2, id1]), [50, 100])
        self.assertListEqual(result, ['First Done', 'Second Done'])

    def test_data(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1(set_progress):
            self.first_done.wait()
            set_progress(data={'thread_id': 1})
            self.second_done.wait()
            set_progress(data={'return': 2})
            return

        result = []

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1)

        self.ao.start()
        self.assertDictEqual({}, self.ao.data(id1))
        self.first_done.set()
        # force context switch
        time.sleep(0.001)
        self.assertDictEqual({'thread_id': 1}, self.ao.data(id1))

        self.second_done.set()
        # force context switch
        time.sleep(0.001)
        self.assertDictEqual({'thread_id': 1, 'return': 2}, self.ao.data(id1))

    def test_wait_data(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1(set_progress):
            self.first_done.wait()
            set_progress(data={'thread_id': 1})
            self.second_done.set()
            return

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1, )

        self.ao.start()
        r = self.ao.wait_data(id1, 'thread_id', timeout=0.1)

        self.assertFalse(r)
        self.first_done.set()
        self.second_done.wait()
        r = self.ao.wait_data(id1, 'thread_id', timeout=0.1)

        self.assertEqual(1, r)

    def test_error(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1():
            raise RuntimeError('Error')

        result = []

        self.ao = AsyncOperator(priority=False, start=False)

        id1 = self.ao.register(process1, callback=lambda data: result.append(data.returndata))

        self.ao.start()

        self.ao.wait_tasks(id1)

        self.assertEqual(self.ao.status(id1), TaskStatus.ERROR)
        self.assertIsInstance(self.ao.exception(id1), RuntimeError)

    def test_num_tasks_in_state(self):
        import threading

        self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1():
            self.first_done.wait()
            return 'First Done'

        def process2():
            self.second_done.wait()
            raise RuntimeError('Error')

        result = []

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1, callback=lambda data: result.append(data.returndata))
        id2 = self.ao.register(process2, callback=lambda data: result.append(data.returndata))

        self.assertRaises(RuntimeError, self.ao.wait_tasks, (id1,))

        self.assertEqual(2, self.ao.num_tasks_in_state(TaskStatus.PENDING))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.RUNNING))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.FINISHED))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.ERROR))
        self.assertEqual(2, self.ao.num_tasks_in_state())

        self.ao.start()

        while self.ao.num_tasks_in_state(TaskStatus.RUNNING) != 2:
            time.sleep(0.001)

        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.PENDING))
        self.assertEqual(2, self.ao.num_tasks_in_state(TaskStatus.RUNNING))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.FINISHED))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.ERROR))
        self.assertEqual(2, self.ao.num_tasks_in_state())

        self.first_done.set()
        self.ao.wait_tasks(id1)

        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.PENDING))
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.RUNNING))
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.FINISHED))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.ERROR))
        self.assertEqual(2, self.ao.num_tasks_in_state())

        self.second_done.set()
        self.ao.wait_tasks(id2)

        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.PENDING))
        self.assertEqual(0, self.ao.num_tasks_in_state(TaskStatus.RUNNING))
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.FINISHED))
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.ERROR))
        self.assertEqual(2, self.ao.num_tasks_in_state())

    def test_purge(self):
        import threading

        # self.first_done = threading.Event()
        self.second_done = threading.Event()

        def process1():
            # self.first_done.wait()
            return 'First Done'

        def process2():
            self.second_done.wait()
            raise RuntimeError('Error')

        result = []

        self.ao = AsyncOperator(priority=False)

        id1 = self.ao.register(process1, callback=lambda data: result.append(data.returndata))
        id2 = self.ao.register(process2, callback=lambda data: result.append(data.returndata))

        self.assertRaises(RuntimeError, self.ao.wait_tasks, (id1,))

        self.ao.start()

        self.ao.wait_tasks(id1)

        self.assertEqual(2, self.ao.num_tasks_in_state())
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.PENDING, TaskStatus.RUNNING))
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.FINISHED))

        self.ao.purge()
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.PENDING, TaskStatus.RUNNING))
        self.assertEqual(1, self.ao.num_tasks_in_state())

        self.second_done.set()
        self.ao.wait_tasks(id2)
        self.assertEqual(1, self.ao.num_tasks_in_state(TaskStatus.ERROR))
        self.assertEqual(1, self.ao.num_tasks_in_state())
        self.ao.purge()

        self.assertEqual(0, self.ao.num_tasks_in_state())
        self.assertEqual(2, len(result))
