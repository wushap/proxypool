from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppSettings:
    project_root: Path
    db_path: Path
    output_dir: Path
    sources_file: Path
    singbox_routes_file: Path
    singbox_runtime_config_file: Path
    singbox_runtime_log_file: Path
    singbox_binary: str
    test_url: str
    api_key: str
    backend_engine: str
    backend_health_check_sec: int
    backend_auto_restart_max: int
    http_gateway_default_host: str = "127.0.0.1"
    http_gateway_default_port: int = 8899
    mihomo_binary: str = "mihomo"
    mihomo_runtime_dir: Path = Path("data/runtime/mihomo")


def load_settings() -> AppSettings:
    project_root = Path(__file__).resolve().parents[1]
    local_singbox = project_root / "bin" / "sing-box"
    db_path = Path(os.getenv("PROXYPOOL_DB_PATH", str(project_root / "data" / "proxies.db")))
    output_dir = Path(os.getenv("PROXYPOOL_OUTPUT_DIR", str(project_root / "output")))
    sources_file = Path(os.getenv("PROXYPOOL_SOURCES_FILE", str(project_root / "configs" / "sources.txt")))
    singbox_routes_file = Path(
        os.getenv("PROXYPOOL_SINGBOX_ROUTES_FILE", str(project_root / "configs" / "singbox-routes.json"))
    )
    singbox_runtime_config_file = Path(
        os.getenv("PROXYPOOL_SINGBOX_RUNTIME_CONFIG", str(project_root / "data" / "runtime" / "singbox.json"))
    )
    singbox_runtime_log_file = Path(
        os.getenv("PROXYPOOL_SINGBOX_RUNTIME_LOG", str(project_root / "data" / "runtime" / "singbox.log"))
    )
    singbox_binary = os.getenv(
        "PROXYPOOL_SINGBOX_BINARY",
        str(local_singbox if local_singbox.exists() else "sing-box"),
    )
    test_url = os.getenv("PROXYPOOL_TEST_URL", "https://www.cloudflare.com/cdn-cgi/trace")
    api_key = os.getenv("PROXYPOOL_API_KEY", "")
    http_gateway_default_host = os.getenv("PROXYPOOL_HTTP_GATEWAY_DEFAULT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    http_gateway_default_port = max(1, min(65535, int(os.getenv("PROXYPOOL_HTTP_GATEWAY_DEFAULT_PORT", "8899"))))
    backend_engine = os.getenv("PROXYPOOL_BACKEND_ENGINE", "singbox").strip().lower() or "singbox"
    backend_health_check_sec = max(5, int(os.getenv("PROXYPOOL_BACKEND_HEALTH_CHECK_SEC", "30")))
    backend_auto_restart_max = max(0, int(os.getenv("PROXYPOOL_BACKEND_AUTO_RESTART_MAX", "3")))
    mihomo_binary = os.getenv("PROXYPOOL_MIHOMO_BINARY", "").strip() or _default_mihomo_binary(project_root)
    mihomo_runtime_dir = Path(
        os.getenv("PROXYPOOL_MIHOMO_RUNTIME_DIR", str(project_root / "data" / "runtime" / "mihomo"))
    )

    return AppSettings(
        project_root=project_root,
        db_path=db_path,
        output_dir=output_dir,
        sources_file=sources_file,
        singbox_routes_file=singbox_routes_file,
        singbox_runtime_config_file=singbox_runtime_config_file,
        singbox_runtime_log_file=singbox_runtime_log_file,
        singbox_binary=singbox_binary,
        test_url=test_url,
        api_key=api_key,
        http_gateway_default_host=http_gateway_default_host,
        http_gateway_default_port=http_gateway_default_port,
        backend_engine=backend_engine,
        backend_health_check_sec=backend_health_check_sec,
        backend_auto_restart_max=backend_auto_restart_max,
        mihomo_binary=mihomo_binary,
        mihomo_runtime_dir=mihomo_runtime_dir,
    )


def _default_mihomo_binary(project_root: Path) -> str:
    candidates = [
        project_root / "bin" / "mihomo",
        project_root.parent / "proxy" / "mihomo" / "mihomo",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "mihomo"
