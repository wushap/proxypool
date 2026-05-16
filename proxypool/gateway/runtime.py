from __future__ import annotations

import asyncio


class ForwardProxyGatewayRuntime:
    def __init__(self, gateway) -> None:
        self.gateway = gateway
        self.server: asyncio.base_events.Server | None = None
        self.last_error = ""

    async def start(self) -> None:
        self.last_error = ""

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def status(self) -> dict[str, object]:
        return {
            "running": self.server is not None,
            "last_error": self.last_error,
        }
