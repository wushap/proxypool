from pathlib import Path

WEBUI_DIR = Path("proxypool/webui")


def _read_webui() -> str:
    """Read Vite WebUI source files for combined content checks."""
    parts = []
    for name in ["index.html", "package.json", "vite.config.js"]:
        p = WEBUI_DIR / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    src_dir = WEBUI_DIR / "src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*")):
            if p.suffix in {".vue", ".js", ".css"}:
                parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_webui_should_poll_task_list_not_single_task_endpoint() -> None:
    content = _read_webui()
    assert "/api/tasks?limit=" in content
    assert "fetch(`/api/tasks/${taskId}`)" not in content


def test_webui_should_render_multi_task_panel() -> None:
    html = _read_webui()
    assert "任务中心" in html
    assert "v-for=\"task in taskItems\"" in html
    assert "删除记录" in html
    assert "taskMessageText(task)" in html


def test_webui_should_support_stop_task_and_unlimited_openai_check() -> None:
    content = _read_webui()
    assert "/api/tasks/${taskId}/stop" in content
    assert "/api/tasks/${taskId}" in content
    assert "isTaskDeletable" in content
    # Check for the openai check task parameters (may be formatted differently)
    assert "only_unchecked: false" in content
    assert "only_available: true" in content


def test_webui_should_start_subscription_refresh_task_from_bulk_button() -> None:
    content = _read_webui()
    assert "/api/tasks/subscriptions-refresh/start?timeout_sec=12" in content
    assert '"订阅刷新任务"' in content
    # Task label mapping (may use object lookup or if/else)
    assert "subscriptions_refresh" in content
    assert "订阅刷新任务" in content


def test_webui_should_support_speed_test_and_auto_tasks() -> None:
    content = _read_webui()
    assert "测试网速" in content
    assert "speedTestForm" in content
    assert "only_direct" in content
    assert "仅对可直连的节点测速" in content
    assert "排除依赖前置代理的链式连通节点" in content
    assert "/api/tasks/speed-test/start" in content
    assert "自动任务" in content
    assert "autoTaskConfig" in content
    assert "/api/tasks/auto-config" in content
