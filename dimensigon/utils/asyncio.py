import sys as _sys
from asyncio import *

if _sys.version_info < (3, 7):
    def _set_task_name(task, name):
        if name is not None:
            try:
                set_name = task.set_name
            except AttributeError:
                pass
            else:
                set_name(name)


    def create_task(coro, *, name=None):
        """Schedule the execution of a coroutine object in a spawn task.

        Return a Task object.
        """
        loop = get_event_loop()
        task = loop.create_task(coro)
        _set_task_name(task, name)
        return task


    def run(aw, *, debug=False):
        # Emulate asyncio.run() on older versions
        loop = new_event_loop()
        set_event_loop(loop)
        loop.set_debug(debug)
        try:
            return loop.run_until_complete(aw)
        except Exception:
            raise
        finally:
            loop.close()
            set_event_loop(None)
