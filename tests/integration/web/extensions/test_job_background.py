import threading
from unittest import TestCase
from unittest.mock import Mock

from dm.web.extensions.job_background import TaskStatus

from dm.web import create_app, ajl


class TestJobBackground(TestCase):

    def test_create_multiple_apps(self):
        app1 = create_app('test')

        app2 = create_app('test')

        with app1.app_context():
            job_id = ajl.register(lambda x: x * 2, (3,))

            # queue.queue.wait_tasks(job_id)
            self.assertEqual([job_id], ajl.queue.tasks_in_state(TaskStatus.FINISHED))

        with app2.app_context():
            # job_id = queue.register(lambda x: x * 2, 3)
            # queue.wait(job_id)

            self.assertEqual([], ajl.queue.tasks_in_state(TaskStatus.FINISHED))

    def test_period_jobs(self):
        mock = Mock()
        event = threading.Event()

        def call_mock():
            mock()
            event.set()

        app = create_app('test')
        with app.app_context():
            ajl.start(0.1)
            ajl.schedule.every(0.2).seconds.do(call_mock)

            event.wait()
            event.clear()
            self.assertEqual(1, mock.call_count)
            event.wait()
            self.assertEqual(2, mock.call_count)
            ajl.stop()
