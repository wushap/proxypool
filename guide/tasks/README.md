# Tasks Module

## Scope

The tasks module provides lightweight in-memory tracking for long-running operations started through API routes.

## Key Files

- `proxypool/tasks/manager.py` defines `TaskManager` and `TaskCancelled`.

## Implementation Notes

`TaskManager.start_task(kind, runner)` creates a task record with queued/running/success/failed/cancelled state, progress counters, result, error text, timestamps, and a cancellation flag. Each task runs in a daemon thread. Runners receive an update callback and, when their signature supports it, a stop callback.

Progress is computed from `completed / total` and stored as a percentage. Terminal states are protected from being overwritten by late non-terminal updates. `stop_task()` requests cancellation and immediately cancels queued tasks; running tasks must cooperate by checking the provided stop callback and raising `TaskCancelled` or returning.

The manager keeps a bounded task history and trims terminal tasks when the maximum is exceeded. State is process-local and not persisted to SQLite.

## Tests

Task behavior is covered by `tests/test_task_manager.py`, `tests/test_tasks.py`, `tests/test_api_tasks_stop.py`, and Web UI task interaction tests.
