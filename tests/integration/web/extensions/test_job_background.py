from unittest import TestCase
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
