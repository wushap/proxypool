#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proxypool.collector.service import CollectorService
from proxypool.settings import load_settings
from proxypool.storage.sqlite import SQLiteProxyStorage


def _read_sources(path: Path) -> list[str]:
    if not path.exists():
        return []
    rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    result: list[str] = []
    for row in rows:
        text = row.strip()
        if not text or text.startswith("#"):
            continue
        result.append(text)
    return result


def main() -> None:
    cfg = load_settings()
    storage = SQLiteProxyStorage(cfg.db_path)
    collector = CollectorService(storage)

    sources = _read_sources(cfg.sources_file)
    report = collector.collect_from_sources(sources)

    summary = {
        "sources_file": str(cfg.sources_file),
        "total_sources": report.total_sources,
        "total_parsed": report.total_parsed,
        "total_inserted": report.total_inserted,
        "total_updated": report.total_updated,
        "total_invalid": report.total_invalid,
        "protocol_distribution": storage.count_by_protocol(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
