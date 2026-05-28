from __future__ import annotations

import inspect
import threading
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


class TaskCancelled(RuntimeError):
    pass


_TERMINAL_STATUSES = {"success", "failed", "cancelled"}


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
                "cancel_requested": False,
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
                current_status = str(task.get("status") or "")
                next_status = str(kwargs.get("status") or "")
                if current_status in _TERMINAL_STATUSES and not kwargs:
                    return
                if (
                    current_status in _TERMINAL_STATUSES
                    and next_status
                    and next_status not in _TERMINAL_STATUSES
                ):
                    return
                if current_status in _TERMINAL_STATUSES and not next_status:
                    return
                for key, value in kwargs.items():
                    task[key] = value
                total = int(task.get("total") or 0)
                completed = int(task.get("completed") or 0)
                task["progress"] = (
                    100.0 if total <= 0 else round(min(1.0, completed / total) * 100.0, 2)
                )
                task["updated_at"] = _utc_now()

        def _should_stop() -> bool:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    return True
                return bool(task.get("cancel_requested"))

        supports_should_stop = _runner_supports_should_stop(runner)

        def _run() -> None:
            if _should_stop():
                _update(status="cancelled", message="cancelled", finished_at=_utc_now())
                return
            _update(status="running", message="running")
            try:
                result = runner(_update, _should_stop) if supports_should_stop else runner(_update)
                if _should_stop():
                    _update(
                        status="cancelled",
                        message="cancelled",
                        result=result,
                        finished_at=_utc_now(),
                    )
                else:
                    _update(
                        status="success", message="success", result=result, finished_at=_utc_now()
                    )
            except TaskCancelled as exc:
                _update(
                    status="cancelled",
                    message="cancelled",
                    error=str(exc),
                    finished_at=_utc_now(),
                )
            except Exception as exc:  # pragma: no cover - exercised in runtime
                if _should_stop():
                    _update(
                        status="cancelled",
                        message="cancelled",
                        error=str(exc),
                        finished_at=_utc_now(),
                    )
                    return
                _update(
                    status="failed",
                    message="failed",
                    error=f"{exc}\n{traceback.format_exc(limit=4)}",
                    finished_at=_utc_now(),
                )

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return task_id

    def stop_task(self, task_id: str) -> bool:
        now = _utc_now()
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            status = str(task.get("status") or "")
            if status in _TERMINAL_STATUSES:
                return False
            task["cancel_requested"] = True
            task["updated_at"] = now
            task["message"] = "cancel requested"
            if status == "queued":
                task["status"] = "cancelled"
                task["message"] = "cancelled"
                task["finished_at"] = now
                task["progress"] = 100.0
            return True

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return dict(task)

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            status = str(task.get("status") or "")
            if status not in _TERMINAL_STATUSES:
                return False
            self._tasks.pop(task_id, None)
            self._order = [item for item in self._order if item != task_id]
            return True

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
            if task.get("status") in _TERMINAL_STATUSES:
                self._tasks.pop(task_id, None)
        self._order = [task_id for task_id in self._order if task_id in self._tasks]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _runner_supports_should_stop(runner: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(runner)
    except Exception:
        return False
    params = list(sig.parameters.values())
    has_varargs = any(
        p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in params
    )
    return has_varargs or len(params) >= 2
