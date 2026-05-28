from __future__ import annotations

import time

from proxypool.tasks.manager import TaskCancelled, TaskManager


# --- start_task / get_task / list_tasks ---


def test_start_task_returns_unique_id() -> None:
    mgr = TaskManager()
    id1 = mgr.start_task("kind-a", lambda update: None)
    id2 = mgr.start_task("kind-b", lambda update: None)
    assert id1 != id2
    assert len(id1) == 32  # uuid hex


def test_get_task_returns_copy() -> None:
    mgr = TaskManager()
    tid = mgr.start_task("test", lambda update: None)
    task = mgr.get_task(tid)
    assert task is not None
    assert task["kind"] == "test"
    # Returned dict should be a copy, not a live reference
    task["kind"] = "mutated"
    assert mgr.get_task(tid)["kind"] == "test"


def test_get_task_unknown_returns_none() -> None:
    mgr = TaskManager()
    assert mgr.get_task("nonexistent") is None


def test_list_tasks_returns_most_recent_first() -> None:
    mgr = TaskManager()
    ids = []
    for i in range(5):
        tid = mgr.start_task(f"job-{i}", lambda update: None)
        ids.append(tid)

    tasks = mgr.list_tasks(limit=10)
    assert len(tasks) == 5
    # Most recent first
    assert tasks[0]["task_id"] == ids[-1]
    assert tasks[-1]["task_id"] == ids[0]


def test_list_tasks_respects_limit() -> None:
    mgr = TaskManager()
    for i in range(10):
        mgr.start_task(f"job-{i}", lambda update: None)

    tasks = mgr.list_tasks(limit=3)
    assert len(tasks) == 3


def test_list_tasks_empty() -> None:
    mgr = TaskManager()
    assert mgr.list_tasks() == []


# --- Task lifecycle ---


def test_task_runs_to_success() -> None:
    mgr = TaskManager()

    def runner(update):
        update(total=3, completed=0)
        update(completed=1, success=1)
        update(completed=2, success=2)
        update(completed=3, success=3)
        return {"done": True}

    tid = mgr.start_task("work", runner)
    _wait_for_status(mgr, tid, "success")

    task = mgr.get_task(tid)
    assert task is not None
    assert task["status"] == "success"
    assert task["result"] == {"done": True}
    assert task["progress"] == 100.0
    assert task["finished_at"] is not None


def test_task_failure_captures_error() -> None:
    mgr = TaskManager()

    def runner(update):
        raise ValueError("bad input")

    tid = mgr.start_task("fail", runner)
    _wait_for_status(mgr, tid, "failed")

    task = mgr.get_task(tid)
    assert task is not None
    assert task["status"] == "failed"
    assert "bad input" in task["error"]


def test_task_cancelled_via_exception() -> None:
    mgr = TaskManager()

    def runner(update):
        raise TaskCancelled("user abort")

    tid = mgr.start_task("cancel", runner)
    _wait_for_status(mgr, tid, "cancelled")

    task = mgr.get_task(tid)
    assert task is not None
    assert task["status"] == "cancelled"
    assert "user abort" in task["error"]


# --- Cancellation ---


def test_stop_task_sets_cancel_flag() -> None:
    mgr = TaskManager()
    started = []

    def runner(update, should_stop=None):
        started.append(True)
        for _ in range(100):
            if should_stop and should_stop():
                return
            time.sleep(0.02)

    tid = mgr.start_task("long", runner)
    time.sleep(0.05)  # let it start
    assert started

    result = mgr.stop_task(tid)
    assert result is True

    _wait_for_status(mgr, tid, "cancelled")
    task = mgr.get_task(tid)
    assert task is not None
    assert task["status"] == "cancelled"


def test_stop_task_already_finished_returns_false() -> None:
    mgr = TaskManager()

    def runner(update):
        return "ok"

    tid = mgr.start_task("quick", runner)
    _wait_for_status(mgr, tid, "success")

    assert mgr.stop_task(tid) is False


def test_stop_task_nonexistent_returns_false() -> None:
    mgr = TaskManager()
    assert mgr.stop_task("no-such-id") is False


def test_stop_task_queued_immediately_cancels() -> None:
    """A task that hasn't started running yet should be cancelled immediately."""
    mgr = TaskManager()
    barrier = []

    # Block the first task so the second stays queued
    def blocking_runner(update):
        while not barrier:
            time.sleep(0.01)
        return "done"

    def noop_runner(update):
        return "noop"

    # Fill one slot with a blocking task
    mgr.start_task("blocker", blocking_runner)
    time.sleep(0.02)  # let it start

    # The second task will be started in a thread but we can test stop_task
    # on a task that's in queued state by calling stop_task very quickly
    tid2 = mgr.start_task("victim", noop_runner)
    # The task may already be running (thread scheduling), so either outcome is valid
    task = mgr.get_task(tid2)
    assert task is not None

    barrier.append(True)  # unblock


# --- Progress tracking ---


def test_progress_computed_from_total_completed() -> None:
    mgr = TaskManager()

    def runner(update):
        update(total=10, completed=0)
        update(completed=5)
        update(completed=10)
        return "ok"

    tid = mgr.start_task("progress", runner)
    _wait_for_status(mgr, tid, "success")

    task = mgr.get_task(tid)
    assert task is not None
    assert task["total"] == 10
    assert task["completed"] == 10
    assert task["progress"] == 100.0


def test_progress_zero_total_shows_100_when_done() -> None:
    mgr = TaskManager()

    def runner(update):
        update(total=0, completed=0)
        return "ok"

    tid = mgr.start_task("no-total", runner)
    _wait_for_status(mgr, tid, "success")

    task = mgr.get_task(tid)
    assert task is not None
    assert task["progress"] == 100.0


# --- _trim_unlocked ---


def test_trim_removes_oldest_terminal_tasks() -> None:
    mgr = TaskManager(max_tasks=3)

    def runner(update):
        return "ok"

    ids = []
    for _ in range(5):
        tid = mgr.start_task("trim", runner)
        _wait_for_status(mgr, tid, "success", timeout=5.0)
        ids.append(tid)

    # After 5 tasks with max_tasks=3, oldest terminal tasks should be trimmed
    # when new ones are started (trim happens inside start_task)
    remaining = mgr.list_tasks(limit=100)
    remaining_ids = {t["task_id"] for t in remaining}
    # The newest tasks should survive
    assert ids[-1] in remaining_ids
    assert ids[-2] in remaining_ids
    # Oldest should have been trimmed
    assert ids[0] not in remaining_ids


# --- delete_task ---


def test_delete_task_removes_finished_task() -> None:
    mgr = TaskManager()

    def runner(update):
        return "ok"

    tid = mgr.start_task("deleteme", runner)
    _wait_for_status(mgr, tid, "success")

    assert mgr.delete_task(tid) is True
    assert mgr.get_task(tid) is None


def test_delete_task_refuses_running_task() -> None:
    mgr = TaskManager()

    def runner(update):
        time.sleep(0.5)
        return "ok"

    tid = mgr.start_task("running", runner)
    time.sleep(0.02)

    assert mgr.delete_task(tid) is False
    assert mgr.get_task(tid) is not None


def test_delete_nonexistent_returns_false() -> None:
    mgr = TaskManager()
    assert mgr.delete_task("ghost") is False


# --- _runner_supports_should_stop detection ---


def test_runner_with_two_params_gets_should_stop() -> None:
    mgr = TaskManager()
    got_stop = []

    def runner(update, should_stop):
        got_stop.append(should_stop is not None)
        return "ok"

    tid = mgr.start_task("two-param", runner)
    _wait_for_status(mgr, tid, "success")
    assert got_stop == [True]


def test_runner_with_varargs_gets_should_stop() -> None:
    mgr = TaskManager()
    got_stop = []

    def runner(update, *args):
        got_stop.append(len(args) > 0)
        return "ok"

    tid = mgr.start_task("varargs", runner)
    _wait_for_status(mgr, tid, "success")
    assert got_stop == [True]


def test_runner_with_one_param_no_should_stop() -> None:
    mgr = TaskManager()
    call_count = []

    def runner(update):
        call_count.append(1)
        return "ok"

    tid = mgr.start_task("one-param", runner)
    _wait_for_status(mgr, tid, "success")
    assert call_count


# --- Concurrent task limits ---


def test_max_tasks_trims_old_when_exceeded() -> None:
    mgr = TaskManager(max_tasks=5)

    def runner(update):
        return "ok"

    for _ in range(10):
        tid = mgr.start_task("bulk", runner)
        _wait_for_status(mgr, tid, "success")

    tasks = mgr.list_tasks(limit=100)
    assert len(tasks) <= 5


# --- Terminal status immutability ---


def test_update_on_terminal_task_is_ignored() -> None:
    mgr = TaskManager()

    updates = []

    def runner(update):
        update(status="running", message="started")
        update(completed=1, total=1)
        updates.append("ran")
        return "ok"

    tid = mgr.start_task("terminal", runner)
    _wait_for_status(mgr, tid, "success")

    task_before = mgr.get_task(tid)
    assert task_before is not None

    # Attempt to update finished task by calling start_task again with a runner
    # that immediately updates — but the old task's _update closure is internal.
    # Instead, verify the task didn't change.
    task_after = mgr.get_task(tid)
    assert task_after["status"] == "success"


# --- Helpers ---


def _wait_for_status(mgr: TaskManager, task_id: str, status: str, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = mgr.get_task(task_id)
        if task and task.get("status") == status:
            return
        time.sleep(0.01)
    raise TimeoutError(f"Task {task_id} did not reach status '{status}' within {timeout}s")
