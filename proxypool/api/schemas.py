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


class ProxyBulkDeleteRequest(BaseModel):
    normalized_keys: list[str] = Field(default_factory=list)


class SingleProxyTestRequest(BaseModel):
    normalized_key: str
    fallback_front_proxy_keys: list[str] = Field(default_factory=list)
    fallback_front_max_attempts: int = 0


class SpeedTestRequest(BaseModel):
    url: str = "https://speed.cloudflare.com/__down?bytes=10000000"
    limit: int = Field(default=0, ge=0, le=20000)
    timeout_sec: float = Field(default=30.0, ge=3.0, le=300.0)
    only_available: bool = True


class AutoTaskConfigRequest(BaseModel):
    enabled: bool = False
    subscription_refresh_enabled: bool = True
    subscription_refresh_minutes: int = Field(default=60, ge=1, le=7 * 24 * 60)
    tester_enabled: bool = False
    tester_minutes: int = Field(default=60, ge=1, le=7 * 24 * 60)
    tester_limit: int = Field(default=0, ge=0, le=20000)
    tester_concurrency: int = Field(default=50, ge=1, le=500)
    speed_test_enabled: bool = False
    speed_test_minutes: int = Field(default=120, ge=1, le=7 * 24 * 60)
    speed_test_url: str = "https://speed.cloudflare.com/__down?bytes=10000000"
    speed_test_limit: int = Field(default=0, ge=0, le=20000)
    speed_test_timeout_sec: float = Field(default=30.0, ge=3.0, le=300.0)



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
    format: str = "raw"


class PublishedSubscriptionUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict[str, str] | None = None
    enabled: bool | None = None
    format: str | None = None


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
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    listen: str = "0.0.0.0"
    inbound_type: str = "http"


class ProxyPoolUpdateRequest(BaseModel):
    name: str | None = None
    filters: dict[str, str | list[str]] | None = None
    listen: str | None = None
    inbound_type: str | None = None


class ProxyPoolChainConfigRequest(BaseModel):
    chain_enabled: bool = False
    sticky_ttl_sec: int = Field(default=3600, ge=1, le=7 * 24 * 3600)
    session_missing_action: str = "RANDOM"
    session_header_names: list[str] = Field(default_factory=list)
    session_query_param_names: list[str] = Field(default_factory=list)
    gateway_path_prefix: str = ""


class HttpGatewayConfigRequest(BaseModel):
    enabled: bool = False
    listen_host: str = "127.0.0.1"
    listen_port: int = Field(default=8899, ge=1, le=65535)
    endpoint_id: int = Field(default=0, ge=0)
    default_pool_id: int = Field(default=0, ge=0)
    sticky_ttl_sec: int = Field(default=3600, ge=1, le=7 * 24 * 3600)
    session_missing_action: str = "RANDOM"
    http_session_header_names: list[str] = Field(default_factory=list)
    http_session_query_names: list[str] = Field(default_factory=list)
    connect_session_header_names: list[str] = Field(default_factory=list)


class HttpGatewayTestRequest(BaseModel):
    target_url: str
    endpoint_id: int = Field(default=0, ge=0)
    session_id: str = ""


class HttpProxyEndpointCreateRequest(BaseModel):
    name: str
    listen_host: str = "127.0.0.1"
    listen_port: int = Field(default=8899, ge=1, le=65535)
    inbound_type: str = "http"
    enabled: bool = True
    sticky_ttl_sec: int = Field(default=3600, ge=1, le=7 * 24 * 3600)
    session_missing_action: str = "RANDOM"
    session_header_names: list[str] = Field(default_factory=list)
    session_query_param_names: list[str] = Field(default_factory=list)
    connect_session_header_names: list[str] = Field(default_factory=list)
    hop_pool_ids: list[int] = Field(default_factory=list)


class HttpProxyEndpointUpdateRequest(BaseModel):
    name: str | None = None
    listen_host: str | None = None
    listen_port: int | None = Field(default=None, ge=1, le=65535)
    inbound_type: str | None = None
    enabled: bool | None = None
    sticky_ttl_sec: int | None = Field(default=None, ge=1, le=7 * 24 * 3600)
    session_missing_action: str | None = None
    session_header_names: list[str] | None = None
    session_query_param_names: list[str] | None = None
    connect_session_header_names: list[str] | None = None
    hop_pool_ids: list[int] | None = None


class ChainInstanceCreateRequest(BaseModel):
    instance_id: str
    front_node_key: str
    exit_node_key: str
    listen: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    inbound_type: str = "http"


class StickyLeaseInheritRequest(BaseModel):
    from_session_id: str
    to_session_id: str


class PoolSessionRuleUpsertRequest(BaseModel):
    headers: list[str] = Field(default_factory=list)
