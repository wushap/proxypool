from __future__ import annotations

import os

import uvicorn

from proxypool.api.app import create_app

app = create_app()


if __name__ == "__main__":
    host = os.getenv("PROXYPOOL_WEBUI_HOST", "0.0.0.0").strip() or "0.0.0.0"
    try:
        port = max(1, min(65535, int(os.getenv("PROXYPOOL_WEBUI_PORT", "8080"))))
    except ValueError:
        port = 8080
    uvicorn.run("proxypool.main:app", host=host, port=port, reload=False)
