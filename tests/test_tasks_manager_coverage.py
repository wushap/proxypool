"""Additional coverage tests for proxypool.tasks.manager."""
import threading
import time
import unittest
from unittest.mock import patch

from proxypool.tasks.manager import TaskManager, TaskCancelled, _runner_supports_should_stop


class TestTaskManagerCoverage(unittest.TestCase):

    def _wait_for_status(self, mgr, task_id, statuses, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            task = mgr.get_task(task_id)
            if task and task.get("status") in statuses:
                return task
            time.sleep(0.01)
        return mgr.get_task(task_id)

    # --- _update guard paths (lines 54-66) ---

    def test_update_no_kwargs_on_terminal_task(self):
        """Line 58: _update() with empty kwargs on a terminal task is ignored."""
        mgr = TaskManager()

        def runner(update, should_stop):
            update(total=1, completed=1, status="success", message="done")
            update()  # empty kwargs on terminal -> early return at line 58
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success", "failed"})
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "success")

    def test_update_non_terminal_on_terminal_task(self):
        """Line 64: _update(status='running') on a terminal task is blocked."""
        mgr = TaskManager()

        def runner(update, should_stop):
            update(total=1, completed=1, status="success", message="done")
            update(status="running")  # terminal -> non-terminal blocked at line 64
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success", "failed"})
        self.assertEqual(task["status"], "success")

    def test_update_without_status_on_terminal_task(self):
        """Line 66: _update without 'status' kwarg on a terminal task is ignored."""
        mgr = TaskManager()

        def runner(update, should_stop):
            update(total=1, completed=1, status="success", message="done")
            update(message="ignored")  # no status kwarg on terminal -> line 66
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success", "failed"})
        self.assertEqual(task["status"], "success")

    def test_update_task_removed_from_dict(self):
        """Line 54: _update is a no-op when the task has been removed."""
        mgr = TaskManager()
        removed = threading.Event()

        def runner(update, should_stop):
            update(total=1, completed=1, status="success", message="ok")
            removed.wait(timeout=2.0)
            # Task was removed from _tasks while we waited
            update(message="after removal")  # hits line 54
            return "ok"

        task_id = mgr.start_task("demo", runner)
        self._wait_for_status(mgr, task_id, {"success"})
        # Remove the task from internal storage while runner is alive
        with mgr._lock:
            mgr._tasks.pop(task_id, None)
        removed.set()
        time.sleep(0.1)  # let runner thread finish
        self.assertIsNone(mgr.get_task(task_id))

    # --- stop_task paths (lines 130-147) ---

    def test_stop_queued_task_immediately(self):
        """Lines 143-146: stop_task on a queued task sets cancelled + finished_at."""
        mgr = TaskManager()
        # Manually insert a task in "queued" state (no thread involved)
        task_id = "manual_queued"
        now = "2024-01-01T00:00:00+00:00"
        mgr._tasks[task_id] = {
            "task_id": task_id,
            "kind": "demo",
            "status": "queued",
            "message": "queued",
            "total": 0,
            "completed": 0,
            "success": 0,
            "failed": 0,
            "progress": 0.0,
            "result": None,
            "error": "",
            "cancel_requested": False,
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
        }
        mgr._order.append(task_id)

        result = mgr.stop_task(task_id)
        self.assertTrue(result)
        task = mgr.get_task(task_id)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(task["message"], "cancelled")
        self.assertIsNotNone(task["finished_at"])
        self.assertEqual(task["progress"], 100.0)

    def test_stop_nonexistent_task(self):
        """stop_task returns False for an unknown task id."""
        mgr = TaskManager()
        self.assertFalse(mgr.stop_task("nonexistent"))

    def test_stop_terminal_task(self):
        """stop_task returns False for an already-terminal task."""
        mgr = TaskManager()

        def runner(update):
            update(total=1, completed=1, status="success", message="done")
            return "ok"

        task_id = mgr.start_task("demo", runner)
        self._wait_for_status(mgr, task_id, {"success"})
        self.assertFalse(mgr.stop_task(task_id))

    def test_delete_nonexistent_task(self):
        """delete_task returns False for an unknown task id."""
        mgr = TaskManager()
        self.assertFalse(mgr.delete_task("nonexistent"))

    def test_delete_running_task_fails(self):
        """delete_task returns False for a non-terminal task."""
        mgr = TaskManager()
        event = threading.Event()

        def runner(update, should_stop):
            event.wait(timeout=2.0)
            return "ok"

        task_id = mgr.start_task("demo", runner)
        self._wait_for_status(mgr, task_id, {"running"})
        self.assertFalse(mgr.delete_task(task_id))
        mgr.stop_task(task_id)
        event.set()

    # --- _run cancellation before runner starts (lines 87-88) ---

    def test_cancel_before_runner_executes(self):
        """Runner is cancelled via _should_stop after runner returns."""
        mgr = TaskManager()
        proceed = threading.Event()

        def runner(update, should_stop):
            proceed.wait(timeout=10.0)
            return "done"

        task_id = mgr.start_task("demo", runner)
        mgr.stop_task(task_id)
        proceed.set()  # let runner finish so _run re-checks _should_stop

        task = self._wait_for_status(
            mgr, task_id, {"cancelled"}, timeout=2.0
        )
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "cancelled")

    def test_run_detects_pre_start_cancellation(self):
        """Lines 87-88: _run sees cancel_requested before calling runner."""
        mgr = TaskManager()
        _orig_start = threading.Thread.start
        _thread_event = threading.Event()

        def _delayed_start(self):
            _orig_target = self._target

            def _wrapped(*args, **kwargs):
                _thread_event.wait(timeout=2.0)
                return _orig_target(*args, **kwargs)

            self._target = _wrapped
            _orig_start(self)

        with patch.object(threading.Thread, "start", _delayed_start):
            task_id = mgr.start_task("demo", lambda u, s: None)

        # Thread is blocked on _thread_event; stop_task runs while queued
        mgr.stop_task(task_id)
        # Release the thread -- _run will find cancel_requested already True
        _release = threading.Timer(0.1, _thread_event.set)
        _release.daemon = True
        _release.start()

        task = self._wait_for_status(
            mgr, task_id, {"cancelled"}, timeout=2.0
        )
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "cancelled")

    # --- _trim_unlocked paths (lines 173-184) ---

    def test_trim_removes_terminal_tasks_on_overflow(self):
        """Line 182: trim removes old terminal tasks when count exceeds max."""
        mgr = TaskManager(max_tasks=3)

        def runner(update):
            update(total=1, completed=1, message="done")
            return "ok"

        ids = []
        for _ in range(5):
            tid = mgr.start_task("demo", runner)
            ids.append(tid)
            self._wait_for_status(mgr, tid, {"success"})

        # After 5 starts with max_tasks=3, trim should have cleaned up old tasks
        self.assertLessEqual(len(mgr._order), mgr.max_tasks + 1)

    def test_trim_skips_missing_task_entry(self):
        """Line 181: trim continues past a stale id not in _tasks dict."""
        mgr = TaskManager(max_tasks=1)
        # Insert a stale ID into _order that has no corresponding _tasks entry
        mgr._order.append("stale_nonexistent")
        # Now start a task -- this pushes _order past max_tasks, triggering trim
        # Trim encounters "stale_nonexistent" -> _tasks.get() returns None -> continue

        def runner(update):
            return "ok"

        mgr.start_task("demo", runner)
        # stale_nonexistent should have been cleaned from _order
        self.assertNotIn("stale_nonexistent", mgr._order)

    def test_trim_preserves_non_terminal_overflow(self):
        """Trim does not remove non-terminal tasks even when overflowing."""
        mgr = TaskManager(max_tasks=2)
        event = threading.Event()

        def blocker(update, should_stop):
            event.wait(timeout=2.0)
            return "ok"

        # Start a task that stays running
        tid1 = mgr.start_task("demo", blocker)
        self._wait_for_status(mgr, tid1, {"running"})

        # Start two more -- exceeds max_tasks=2, trim runs
        def runner(update):
            return "ok"

        tid2 = mgr.start_task("demo", runner)
        self._wait_for_status(mgr, tid2, {"success"})
        tid3 = mgr.start_task("demo", runner)
        self._wait_for_status(mgr, tid3, {"success"})

        # The running task should survive trim (not terminal)
        self.assertIn(tid1, mgr._tasks)
        mgr.stop_task(tid1)
        event.set()

    # --- _runner_supports_should_stop (lines 191-200) ---

    def test_supports_should_stop_two_params(self):
        """Returns True for a runner with 2 positional params."""
        def two_params(update, should_stop):
            pass
        self.assertTrue(_runner_supports_should_stop(two_params))

    def test_supports_should_stop_one_param(self):
        """Returns False for a runner with only 1 param."""
        def one_param(update):
            pass
        self.assertFalse(_runner_supports_should_stop(one_param))

    def test_supports_should_stop_varargs(self):
        """Returns True for a runner with *args."""
        def varargs(*args):
            pass
        self.assertTrue(_runner_supports_should_stop(varargs))

    def test_supports_should_stop_exception_path(self):
        """Lines 194-195: returns False when inspect.signature raises."""
        with patch(
            "proxypool.tasks.manager.inspect.signature",
            side_effect=ValueError("cannot introspect"),
        ):
            result = _runner_supports_should_stop(lambda u: None)
        self.assertFalse(result)

    # --- progress calculation ---

    def test_progress_when_total_is_zero(self):
        """Progress is 100.0 when total is 0 (division guarded)."""
        mgr = TaskManager()

        def runner(update, should_stop):
            update(total=0, completed=0, message="no total")
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success"})
        self.assertEqual(task["progress"], 100.0)

    def test_progress_clamped_at_100(self):
        """Progress is clamped at 100.0 even when completed > total."""
        mgr = TaskManager()

        def runner(update, should_stop):
            update(total=5, completed=10, message="over")
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success"})
        self.assertEqual(task["progress"], 100.0)

    # --- list_tasks ---

    def test_list_tasks_respects_limit(self):
        """list_tasks returns at most *limit* entries, newest first."""
        mgr = TaskManager()

        def runner(update):
            update(total=1, completed=1, message="done")
            return "ok"

        ids = []
        for _ in range(5):
            tid = mgr.start_task("demo", runner)
            ids.append(tid)
            self._wait_for_status(mgr, tid, {"success"})

        tasks = mgr.list_tasks(limit=3)
        self.assertEqual(len(tasks), 3)

    def test_list_tasks_empty(self):
        """list_tasks returns an empty list when there are no tasks."""
        mgr = TaskManager()
        self.assertEqual(mgr.list_tasks(), [])

    # --- TaskCancelled exception ---

    def test_runner_raises_task_cancelled(self):
        """Runner raising TaskCancelled marks the task as cancelled."""
        mgr = TaskManager()

        def runner(update, should_stop):
            raise TaskCancelled("user cancelled")

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"cancelled", "failed"})
        self.assertEqual(task["status"], "cancelled")
        self.assertIn("user cancelled", task["error"])

    # --- runner without should_stop ---

    def test_runner_without_should_stop_param(self):
        """Runner with only (update) works when supports_should_stop is False."""
        mgr = TaskManager()

        def runner(update):
            update(total=1, completed=1, message="done")
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success"})
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["result"], "ok")

    # --- task finished_at ---

    def test_finished_at_is_set_on_completion(self):
        """finished_at timestamp is set when the task reaches terminal state."""
        mgr = TaskManager()

        def runner(update):
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task = self._wait_for_status(mgr, task_id, {"success"})
        self.assertIsNotNone(task["finished_at"])

    # --- get_task ---

    def test_get_task_returns_copy(self):
        """get_task returns a snapshot, not a reference to internal state."""
        mgr = TaskManager()

        def runner(update):
            return "ok"

        task_id = mgr.start_task("demo", runner)
        task1 = mgr.get_task(task_id)
        task2 = mgr.get_task(task_id)
        self.assertIsNot(task1, task2)
        self.assertEqual(task1, task2)


if __name__ == "__main__":
    unittest.main()
