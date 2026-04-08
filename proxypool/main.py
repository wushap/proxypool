from __future__ import annotations

import uvicorn

from proxypool.api.app import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run("proxypool.main:app", host="0.0.0.0", port=8080, reload=False)
