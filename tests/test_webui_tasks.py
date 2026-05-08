from pathlib import Path


def test_webui_should_poll_task_list_not_single_task_endpoint() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "/api/tasks?limit=" in html
    assert "fetch(`/api/tasks/${taskId}`)" not in html


def test_webui_should_render_multi_task_panel() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "任务中心" in html
    assert "v-for=\"task in taskItems\"" in html


def test_webui_should_support_stop_task_and_unlimited_openai_check() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "/api/tasks/${taskId}/stop" in html
    assert "/api/tasks/${taskId}" in html
    assert "isTaskDeletable" in html
    assert "{ limit: 0, concurrency, only_unchecked: false, only_available: true }" in html


def test_webui_should_start_subscription_refresh_task_from_bulk_button() -> None:
    html = Path("proxypool/webui/index.html").read_text(encoding="utf-8")
    assert "/api/tasks/subscriptions-refresh/start?timeout_sec=12" in html
    assert '"订阅刷新任务"' in html
    assert 'if (key === "subscriptions_refresh") return "订阅刷新任务";' in html
