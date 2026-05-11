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
    resin_binary: str = "resin"
    resin_port: int = 2260
    resin_admin_token: str = ""
    resin_data_dir: Path = Path("data/resin")
    resin_auto_start: bool = False


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
    backend_engine = os.getenv("PROXYPOOL_BACKEND_ENGINE", "singbox").strip().lower() or "singbox"
    backend_health_check_sec = max(5, int(os.getenv("PROXYPOOL_BACKEND_HEALTH_CHECK_SEC", "30")))
    backend_auto_restart_max = max(0, int(os.getenv("PROXYPOOL_BACKEND_AUTO_RESTART_MAX", "3")))

    local_resin = project_root / "bin" / "resin"
    resin_binary = os.getenv(
        "PROXYPOOL_RESIN_BINARY",
        str(local_resin if local_resin.exists() else "resin"),
    )
    resin_port = max(1, int(os.getenv("PROXYPOOL_RESIN_PORT", "2260")))
    resin_admin_token = os.getenv("PROXYPOOL_RESIN_ADMIN_TOKEN", "")
    resin_data_dir = Path(os.getenv("PROXYPOOL_RESIN_DATA_DIR", str(project_root / "data" / "resin")))
    resin_auto_start = os.getenv("PROXYPOOL_RESIN_AUTO_START", "").strip().lower() in {"1", "true", "yes"}

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
        backend_engine=backend_engine,
        backend_health_check_sec=backend_health_check_sec,
        backend_auto_restart_max=backend_auto_restart_max,
        resin_binary=resin_binary,
        resin_port=resin_port,
        resin_admin_token=resin_admin_token,
        resin_data_dir=resin_data_dir,
        resin_auto_start=resin_auto_start,
    )
