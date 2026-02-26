import queue
import threading
from typing import Callable

class TaskQueue:
    def __init__(self):
        self.q = queue.Queue()
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def _worker(self):
        while True:
            task = self.q.get()
            try:
                task()
            except Exception as e:
                print(f"Task error: {e}")
            self.q.task_done()

    def add(self, func: Callable):
        self.q.put(func)

# singleton
task_queue = TaskQueue()