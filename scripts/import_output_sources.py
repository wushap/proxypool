#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proxypool.collector.service import CollectorService
from proxypool.storage.sqlite import SQLiteProxyStorage


def main() -> None:
    output_dir = ROOT / "output"
    db_path = ROOT / "data" / "proxies.db"

    files: list[Path] = []
    for pattern in ("*.txt", "*.yaml", "*.yml"):
        files.extend(sorted(output_dir.glob(pattern)))

    storage = SQLiteProxyStorage(db_path)
    service = CollectorService(storage)
    report = service.collect_from_files(files)

    summary = {
        "total_sources": report.total_sources,
        "total_parsed": report.total_parsed,
        "total_inserted": report.total_inserted,
        "total_updated": report.total_updated,
        "total_invalid": report.total_invalid,
        "protocol_distribution": storage.count_by_protocol(),
        "db_path": str(db_path),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
