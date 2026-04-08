#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proxypool.settings import load_settings
from proxypool.storage.sqlite import SQLiteProxyStorage
from proxypool.tester.service import TesterService
from proxypool.tester.singbox import SingboxProber


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one testing batch")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=60)
    parser.add_argument("--timeout-sec", type=float, default=3.0)
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    cfg = load_settings()
    storage = SQLiteProxyStorage(cfg.db_path)
    prober = SingboxProber(
        binary=cfg.singbox_binary,
        test_url=cfg.test_url,
        timeout_sec=args.timeout_sec,
    )
    tester = TesterService(storage, prober=prober)
    report = await tester.run_batch(limit=args.limit, concurrency=args.concurrency)
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
