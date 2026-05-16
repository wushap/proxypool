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


class BackendInstanceCreateRequest(BaseModel):
    instance_id: str = "default"


class GeoEnrichRequest(BaseModel):
    limit: int = 0
    concurrency: int = Field(default=20, ge=1, le=500)


class RunTestRequest(BaseModel):
    limit: int = 0
    concurrency: int = 50
    only_unchecked: bool = False
    only_available: bool = False
    only_unavailable: bool = False
    min_last_checked_age_hours: int = Field(default=0, ge=0, le=24 * 365)
    protocols: list[str] | None = None
    fallback_front_proxy_keys: list[str] = Field(default_factory=list)
    fallback_front_max_attempts: int = 0
    replace_failed_with_available: bool = False


class SingleProxyTestRequest(BaseModel):
    normalized_key: str
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


class PublishedSubscriptionCreateRequest(BaseModel):
    name: str
    filters: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class PublishedSubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict[str, str] | None = None
    enabled: bool | None = None


class BackendPortRangeRequest(BaseModel):
    start: int = Field(default=1081, ge=1, le=65535)
    end: int = Field(default=1180, ge=1, le=65535)


class BackendDefaultListenRequest(BaseModel):
    listen: str = "127.0.0.1"


class SubscriptionRefreshRequest(BaseModel):
    timeout_sec: float = 12.0


class ProxyListResponse(BaseModel):
    total: int
    items: list[dict]


class GenericMessage(BaseModel):
    message: str


class ProxyPoolCreateRequest(BaseModel):
    name: str
    filters: dict[str, str] = Field(default_factory=dict)
    listen: str = "0.0.0.0"
    inbound_type: str = "http"


class ProxyPoolUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict[str, str] | None = None
    listen: str | None = None
    inbound_type: str | None = None


class ProxyPoolChainConfigRequest(BaseModel):
    chain_enabled: bool = False
    sticky_ttl_sec: int = Field(default=3600, ge=1, le=7 * 24 * 3600)
    session_missing_action: str = "RANDOM"
    session_header_names: list[str] = Field(default_factory=list)
    session_query_param_names: list[str] = Field(default_factory=list)
    gateway_path_prefix: str = ""


class ChainInstanceCreateRequest(BaseModel):
    instance_id: str
    front_node_key: str
    exit_node_key: str
    listen: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    inbound_type: str = "http"
