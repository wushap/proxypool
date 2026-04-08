from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable


class TaskManager:
    def __init__(self, max_tasks: int = 200) -> None:
        self.max_tasks = max_tasks
        self._tasks: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def start_task(self, kind: str, runner: Callable[[Callable[..., None]], Any]) -> str:
        task_id = uuid.uuid4().hex
        now = _utc_now()
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "kind": kind,
                "status": "queued",
                "message": "queued",
                "total": 0,
                "completed": 0,
                "success": 0,
                "failed": 0,
                "progress": 0.0,
                "result": None,
                "error": "",
                "started_at": now,
                "updated_at": now,
                "finished_at": None,
            }
            self._order.append(task_id)
            self._trim_unlocked()

        def _update(**kwargs: Any) -> None:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    return
                for key, value in kwargs.items():
                    task[key] = value
                total = int(task.get("total") or 0)
                completed = int(task.get("completed") or 0)
                task["progress"] = 100.0 if total <= 0 else round(min(1.0, completed / total) * 100.0, 2)
                task["updated_at"] = _utc_now()

        def _run() -> None:
            _update(status="running", message="running")
            try:
                result = runner(_update)
                _update(status="success", message="success", result=result, finished_at=_utc_now())
            except Exception as exc:  # pragma: no cover - exercised in runtime
                _update(
                    status="failed",
                    message="failed",
                    error=f"{exc}\n{traceback.format_exc(limit=4)}",
                    finished_at=_utc_now(),
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return dict(task)

    def list_tasks(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(reversed(self._order[-limit:]))
            return [dict(self._tasks[i]) for i in ids if i in self._tasks]

    def _trim_unlocked(self) -> None:
        if len(self._order) <= self.max_tasks:
            return
        overflow = len(self._order) - self.max_tasks
        stale_ids = self._order[:overflow]
        for task_id in stale_ids:
            task = self._tasks.get(task_id)
            if not task:
                continue
            if task.get("status") in {"success", "failed"}:
                self._tasks.pop(task_id, None)
        self._order = [task_id for task_id in self._order if task_id in self._tasks]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
