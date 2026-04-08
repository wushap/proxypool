import time
import unittest

from proxypool.tasks.manager import TaskManager


class TestTaskManager(unittest.TestCase):
    def test_start_and_query_task(self) -> None:
        mgr = TaskManager()

        def runner(update):
            update(total=5, completed=1, success=1, failed=0, message="step1")
            time.sleep(0.02)
            update(total=5, completed=5, success=4, failed=1, message="step2")
            return {"ok": True}

        task_id = mgr.start_task("demo", runner)

        for _ in range(50):
            task = mgr.get_task(task_id)
            if task and task.get("status") in {"success", "failed"}:
                break
            time.sleep(0.02)

        task = mgr.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["total"], 5)
        self.assertEqual(task["completed"], 5)
        self.assertEqual(task["success"], 4)
        self.assertEqual(task["failed"], 1)
        self.assertEqual(task["result"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
