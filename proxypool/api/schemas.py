from __future__ import annotations

from pydantic import BaseModel, Field


class ImportFilesRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)


class ImportTextItem(BaseModel):
    filename: str = "upload.txt"
    content: str = ""


class ImportTextsRequest(BaseModel):
    items: list[ImportTextItem] = Field(default_factory=list)


class ImportUrlsRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    timeout_sec: float = 12.0


class ImportSourcesRequest(BaseModel):
    sources: list[str] = Field(default_factory=list)
    timeout_sec: float = 12.0


class SingboxRouteItem(BaseModel):
    inbound_port: int
    proxy_key: str = ""
    front_proxy_key: str = ""
    middle_proxy_key: str = ""
    exit_proxy_key: str = ""
    inbound_type: str = "http"
    listen: str = "127.0.0.1"


class SetSingboxRoutesRequest(BaseModel):
    routes: list[SingboxRouteItem] = Field(default_factory=list)
    auto_restart: bool = False


class GeoEnrichRequest(BaseModel):
    limit: int = 200
    concurrency: int = Field(default=20, ge=1, le=500)


class RunTestRequest(BaseModel):
    limit: int = 0
    concurrency: int = 50
    only_unchecked: bool = False
    only_available: bool = False
    protocols: list[str] | None = None
    fallback_front_proxy_keys: list[str] = Field(default_factory=list)
    fallback_front_max_attempts: int = 0


class SubscriptionCreateRequest(BaseModel):
    name: str
    url: str
    enabled: bool = True


class SubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


class SubscriptionUpdateProxyRequest(BaseModel):
    update_proxy_key: str = ""


class SubscriptionRefreshRequest(BaseModel):
    timeout_sec: float = 12.0


class ProxyListResponse(BaseModel):
    total: int
    items: list[dict]


class GenericMessage(BaseModel):
    message: str
