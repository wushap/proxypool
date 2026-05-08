from __future__ import annotations

import time

from proxypool.tasks.manager import TaskManager


def test_task_manager_supports_parallel_tasks() -> None:
    manager = TaskManager(max_tasks=20)

    def _runner(name: str):
        def _run(update):
            update(total=2, completed=0, message=f"{name} 0/2")
            time.sleep(0.05)
            update(total=2, completed=1, success=1, message=f"{name} 1/2")
            time.sleep(0.05)
            update(total=2, completed=2, success=2, message=f"{name} 2/2")
            return {"name": name}

        return _run

    t1 = manager.start_task("job-a", _runner("a"))
    t2 = manager.start_task("job-b", _runner("b"))
    assert t1 != t2

    # wait until both finished
    deadline = time.time() + 2.0
    while time.time() < deadline:
        a = manager.get_task(t1)
        b = manager.get_task(t2)
        if a and b and a.get("status") == "success" and b.get("status") == "success":
            break
        time.sleep(0.02)

    a = manager.get_task(t1)
    b = manager.get_task(t2)
    assert a is not None and b is not None
    assert a["status"] == "success"
    assert b["status"] == "success"
    assert float(a.get("progress") or 0) >= 100
    assert float(b.get("progress") or 0) >= 100

