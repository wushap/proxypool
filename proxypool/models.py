from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any


@dataclass(slots=True)
class ProxyNode:
    protocol: str
    host: str
    port: int
    raw_link: str
    name: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def normalized_key(self) -> str:
        identity = self.extra.get("uuid") or self.extra.get("password") or self.extra.get("username") or ""
        base = f"{self.protocol}|{self.host}|{self.port}|{identity}"
        return sha1(base.encode("utf-8")).hexdigest()
