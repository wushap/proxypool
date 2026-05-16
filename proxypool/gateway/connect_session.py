from __future__ import annotations

import secrets


class ConnectSessionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def get_or_create(self, connection_id: str) -> str:
        key = str(connection_id or "").strip()
        if key not in self._items:
            self._items[key] = f"connect:{secrets.token_hex(8)}"
        return self._items[key]

    def drop(self, connection_id: str) -> None:
        self._items.pop(str(connection_id or "").strip(), None)
