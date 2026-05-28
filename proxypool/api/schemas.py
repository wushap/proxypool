from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from proxypool.security.url_validator import is_safe_url


class ImportFilesRequest(BaseModel):
    """导入文件请求"""

    paths: list[str] = Field(default_factory=list, description="要导入的文件路径列表")


class ImportTextItem(BaseModel):
    """导入文本项"""

    filename: str = Field(description="文件名，用于标识内容来源")
    content: str = Field(default="", description="文件内容")


class ImportTextsRequest(BaseModel):
    """从文本导入请求"""

    items: list[ImportTextItem] = Field(default_factory=list, description="文本项列表")


class ImportUrlsRequest(BaseModel):
    """从URL导入请求"""

    urls: list[str] = Field(default_factory=list, description="要导入的URL列表")
    timeout_sec: float = Field(
        default=12.0, ge=1.0, le=120.0, description="每个URL的请求超时时间（秒）"
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        """Validate URLs to prevent SSRF attacks."""
        for url in v:
            is_safe, error = is_safe_url(url)
            if not is_safe:
                raise ValueError(f"URL validation failed: {error}")
        return v


class ImportSourcesRequest(BaseModel):
    """从订阅源导入请求"""

    sources: list[str] = Field(default_factory=list, description="订阅源URL或文件路径列表")
    timeout_sec: float = Field(
        default=12.0, ge=1.0, le=120.0, description="每个源的请求超时时间（秒）"
    )

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v: list[str]) -> list[str]:
        """Validate source URLs to prevent SSRF attacks."""
        for source in v:
            # Sources can be URLs or file paths
            if source.startswith(("http://", "https://")):
                is_safe, error = is_safe_url(source)
                if not is_safe:
                    raise ValueError(f"Source URL validation failed: {error}")
        return v


class SingboxRouteItem(BaseModel):
    """SingBox路由配置项"""

    inbound_port: int = Field(ge=1, le=65535, description="入站端口号")
    proxy_key: str = Field(default="", description="代理节点密钥")
    front_proxy_key: str = Field(default="", description="前置代理节点密钥")
    middle_proxy_key: str = Field(default="", description="中间代理节点密钥")
    exit_proxy_key: str = Field(default="", description="出口代理节点密钥")
    inbound_type: str = Field(
        default="http", pattern="^(http|socks5)$", description="入站类型：http或socks5"
    )
    listen: str = Field(default="127.0.0.1", description="监听地址")


class SetSingboxRoutesRequest(BaseModel):
    """设置SingBox路由请求"""

    routes: list[SingboxRouteItem] = Field(default_factory=list, description="路由配置列表")
    auto_restart: bool = Field(default=False, description="设置后是否自动重启后端")


class BackendInstanceCreateRequest(BaseModel):
    """创建后端实例请求"""

    instance_id: str = Field(default="default", description="实例ID")


class GeoEnrichRequest(BaseModel):
    """地理位置增强请求"""

    limit: int = Field(default=0, ge=0, description="处理数量限制，0表示不限制")
    concurrency: int = Field(default=20, ge=1, le=500, description="并发处理数")


class RunTestRequest(BaseModel):
    """运行测试请求"""

    limit: int = Field(default=0, ge=0, le=20000, description="测试数量限制，0表示不限制")
    concurrency: int = Field(default=50, ge=1, le=500, description="并发测试数")
    only_unchecked: bool = Field(default=False, description="仅测试未检查的节点")
    only_available: bool = Field(default=False, description="仅测试可用节点")
    only_unavailable: bool = Field(default=False, description="仅测试不可用节点")
    min_last_checked_age_hours: int = Field(
        default=0, ge=0, le=24 * 365, description="最小检查间隔（小时）"
    )
    protocols: list[str] | None = Field(default=None, description="指定测试的协议类型列表")
    fallback_front_proxy_keys: list[str] = Field(
        default_factory=list, description="回退前置代理密钥列表"
    )
    fallback_front_max_attempts: int = Field(
        default=0, ge=0, description="回退前置代理最大尝试次数"
    )
    replace_failed_with_available: bool = Field(
        default=False, description="是否用可用节点替换失败节点"
    )


class ProxyBulkDeleteRequest(BaseModel):
    """批量删除代理请求"""

    normalized_keys: list[str] = Field(default_factory=list, description="要删除的代理节点密钥列表")


class SingleProxyTestRequest(BaseModel):
    """单个代理测试请求"""

    normalized_key: str = Field(description="代理节点密钥")
    fallback_front_proxy_keys: list[str] = Field(
        default_factory=list, description="回退前置代理密钥列表"
    )
    fallback_front_max_attempts: int = Field(
        default=0, ge=0, description="回退前置代理最大尝试次数"
    )


class SpeedTestRequest(BaseModel):
    """速度测试请求"""

    url: str = Field(
        default="https://speed.cloudflare.com/__down?bytes=10000000", description="测试目标URL"
    )
    limit: int = Field(default=0, ge=0, le=20000, description="测试数量限制，0表示不限制")
    timeout_sec: float = Field(default=30.0, ge=3.0, le=300.0, description="超时时间（秒）")
    only_available: bool = Field(default=True, description="仅测试可用节点")
    only_direct: bool | None = Field(default=None, description="仅测试直连节点")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate speed test URL to prevent SSRF attacks."""
        if not v:
            return v
        is_safe, error = is_safe_url(v)
        if not is_safe:
            raise ValueError(f"URL validation failed: {error}")
        return v


class AutoTaskConfigRequest(BaseModel):
    """自动任务配置请求"""

    enabled: bool = Field(default=False, description="是否启用自动任务")
    subscription_refresh_enabled: bool = Field(default=True, description="是否启用订阅刷新")
    subscription_refresh_minutes: int = Field(
        default=60, ge=1, le=7 * 24 * 60, description="订阅刷新间隔（分钟）"
    )
    tester_enabled: bool = Field(default=False, description="是否启用自动测试")
    tester_minutes: int = Field(default=60, ge=1, le=7 * 24 * 60, description="测试间隔（分钟）")
    tester_limit: int = Field(default=0, ge=0, le=20000, description="每次测试数量限制")
    tester_concurrency: int = Field(default=50, ge=1, le=500, description="测试并发数")
    speed_test_enabled: bool = Field(default=False, description="是否启用速度测试")
    speed_test_minutes: int = Field(
        default=120, ge=1, le=7 * 24 * 60, description="速度测试间隔（分钟）"
    )
    speed_test_url: str = Field(
        default="https://speed.cloudflare.com/__down?bytes=10000000", description="速度测试目标URL"
    )
    speed_test_limit: int = Field(default=0, ge=0, le=20000, description="速度测试数量限制")
    speed_test_timeout_sec: float = Field(
        default=30.0, ge=3.0, le=300.0, description="速度测试超时时间（秒）"
    )

    @field_validator("speed_test_url")
    @classmethod
    def validate_speed_test_url(cls, v: str) -> str:
        """Validate speed test URL to prevent SSRF attacks."""
        if not v:
            return v
        is_safe, error = is_safe_url(v)
        if not is_safe:
            raise ValueError(f"URL validation failed: {error}")
        return v


class SubscriptionCreateRequest(BaseModel):
    """创建订阅请求"""

    name: str = Field(min_length=1, max_length=200, description="订阅名称")
    url: str = Field(description="订阅URL地址")
    enabled: bool = Field(default=True, description="是否启用")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate subscription URL to prevent SSRF attacks."""
        if not v:
            return v
        is_safe, error = is_safe_url(v)
        if not is_safe:
            raise ValueError(f"URL validation failed: {error}")
        return v


class SubscriptionUpdateRequest(BaseModel):
    """更新订阅请求"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="订阅名称")
    url: str | None = Field(default=None, description="订阅URL地址")
    enabled: bool | None = Field(default=None, description="是否启用")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """Validate subscription URL to prevent SSRF attacks."""
        if v is None:
            return v
        is_safe, error = is_safe_url(v)
        if not is_safe:
            raise ValueError(f"URL validation failed: {error}")
        return v


class SubscriptionUpdateProxyRequest(BaseModel):
    """更新订阅代理请求"""

    update_proxy_key: str = Field(default="", description="用于更新订阅的代理节点密钥")


class PublishedSubscriptionCreateRequest(BaseModel):
    """创建已发布订阅请求"""

    name: str = Field(min_length=1, max_length=200, description="已发布订阅名称")
    filters: dict[str, str] = Field(default_factory=dict, description="过滤条件")
    enabled: bool = Field(default=True, description="是否启用")
    format: str = Field(default="raw", pattern="^(raw|clash)$", description="输出格式：raw或clash")


class PublishedSubscriptionUpdateRequest(BaseModel):
    """更新已发布订阅请求"""

    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="已发布订阅名称"
    )
    filters: dict[str, str] | None = Field(default=None, description="过滤条件")
    enabled: bool | None = Field(default=None, description="是否启用")
    format: str | None = Field(
        default=None, pattern="^(raw|clash)$", description="输出格式：raw或clash"
    )


class BackendPortRangeRequest(BaseModel):
    """后端端口范围请求"""

    start: int = Field(default=1081, ge=1, le=65535, description="起始端口号")
    end: int = Field(default=1180, ge=1, le=65535, description="结束端口号")

    @field_validator("end")
    @classmethod
    def validate_port_range(cls, v: int, info) -> int:
        """验证端口范围：end必须大于start"""
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("结束端口必须大于起始端口")
        return v


class BackendDefaultListenRequest(BaseModel):
    """后端默认监听请求"""

    listen: str = Field(default="127.0.0.1", description="默认监听地址")


class SubscriptionRefreshRequest(BaseModel):
    """订阅刷新请求"""

    timeout_sec: float = Field(default=12.0, ge=1.0, le=120.0, description="刷新超时时间（秒）")


class ProxyListResponse(BaseModel):
    """代理列表响应"""

    total: int = Field(description="总数")
    items: list[dict] = Field(description="代理列表")


class GenericMessage(BaseModel):
    """通用消息响应"""

    message: str = Field(description="消息内容")


class ProxyPoolCreateRequest(BaseModel):
    """创建代理池请求"""

    name: str = Field(min_length=1, max_length=200, description="代理池名称")
    filters: dict[str, str | list[str]] = Field(default_factory=dict, description="过滤条件")
    listen: str = Field(default="0.0.0.0", description="监听地址")
    inbound_type: str = Field(
        default="http", pattern="^(http|socks5)$", description="入站类型：http或socks5"
    )


class ProxyPoolUpdateRequest(BaseModel):
    """更新代理池请求"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="代理池名称")
    filters: dict[str, str | list[str]] | None = Field(default=None, description="过滤条件")
    listen: str | None = Field(default=None, description="监听地址")
    inbound_type: str | None = Field(
        default=None, pattern="^(http|socks5)$", description="入站类型：http或socks5"
    )


class ProxyPoolChainConfigRequest(BaseModel):
    """代理池链式配置请求"""

    chain_enabled: bool = Field(default=False, description="是否启用链式代理")
    sticky_ttl_sec: int = Field(
        default=3600, ge=1, le=7 * 24 * 3600, description="会话保持时间（秒）"
    )
    session_missing_action: str = Field(
        default="RANDOM",
        pattern="^(RANDOM|REJECT|ROUND_ROBIN)$",
        description="会话缺失时的行为：RANDOM/REJECT/ROUND_ROBIN",
    )
    session_header_names: list[str] = Field(default_factory=list, description="会话头字段名列表")
    session_query_param_names: list[str] = Field(
        default_factory=list, description="会话查询参数名列表"
    )
    gateway_path_prefix: str | None = Field(default=None, description="网关路径前缀")


class HttpGatewayConfigRequest(BaseModel):
    """HTTP网关配置请求"""

    enabled: bool = Field(default=False, description="是否启用HTTP网关")
    listen_host: str = Field(default="127.0.0.1", description="监听地址")
    listen_port: int = Field(default=8899, ge=1, le=65535, description="监听端口")
    endpoint_id: int = Field(default=0, ge=0, description="关联的HTTP代理端点ID")
    default_pool_id: int = Field(default=0, ge=0, description="默认代理池ID")
    sticky_ttl_sec: int = Field(
        default=3600, ge=1, le=7 * 24 * 3600, description="会话保持时间（秒）"
    )
    session_missing_action: str = Field(
        default="RANDOM", pattern="^(RANDOM|REJECT|ROUND_ROBIN)$", description="会话缺失时的行为"
    )
    http_session_header_names: list[str] = Field(
        default_factory=list, description="HTTP会话头字段名列表"
    )
    http_session_query_names: list[str] = Field(
        default_factory=list, description="HTTP会话查询参数名列表"
    )
    connect_session_header_names: list[str] = Field(
        default_factory=list, description="CONNECT会话头字段名列表"
    )
    health_check_enabled: bool = Field(default=True, description="是否启用健康检查")
    health_check_interval_sec: int = Field(
        default=30, ge=5, le=3600, description="健康检查间隔（秒）"
    )


class HttpGatewayTestRequest(BaseModel):
    """HTTP网关测试请求"""

    target_url: str = Field(description="测试目标URL")
    endpoint_id: int = Field(default=0, ge=0, description="HTTP代理端点ID")
    session_id: str = Field(default="", description="会话ID")

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, v: str) -> str:
        """Validate gateway test URL to prevent SSRF attacks."""
        if not v:
            return v
        is_safe, error = is_safe_url(v)
        if not is_safe:
            raise ValueError(f"URL validation failed: {error}")
        return v


class HttpProxyEndpointCreateRequest(BaseModel):
    """创建HTTP代理端点请求"""

    name: str = Field(min_length=1, max_length=200, description="端点名称")
    listen_host: str = Field(default="127.0.0.1", description="监听地址")
    listen_port: int = Field(default=8899, ge=1, le=65535, description="监听端口")
    inbound_type: str = Field(default="http", pattern="^(http|socks5)$", description="入站类型")
    enabled: bool = Field(default=True, description="是否启用")
    sticky_ttl_sec: int = Field(
        default=3600, ge=1, le=7 * 24 * 3600, description="会话保持时间（秒）"
    )
    session_missing_action: str = Field(
        default="RANDOM", pattern="^(RANDOM|REJECT|ROUND_ROBIN)$", description="会话缺失时的行为"
    )
    session_header_names: list[str] = Field(default_factory=list, description="会话头字段名列表")
    session_query_param_names: list[str] = Field(
        default_factory=list, description="会话查询参数名列表"
    )
    connect_session_header_names: list[str] = Field(
        default_factory=list, description="CONNECT会话头字段名列表"
    )
    hop_pool_ids: list[int] = Field(default_factory=list, description="跳跃代理池ID列表")


class HttpProxyEndpointUpdateRequest(BaseModel):
    """更新HTTP代理端点请求"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="端点名称")
    listen_host: str | None = Field(default=None, description="监听地址")
    listen_port: int | None = Field(default=None, ge=1, le=65535, description="监听端口")
    inbound_type: str | None = Field(
        default=None, pattern="^(http|socks5)$", description="入站类型"
    )
    enabled: bool | None = Field(default=None, description="是否启用")
    sticky_ttl_sec: int | None = Field(
        default=None, ge=1, le=7 * 24 * 3600, description="会话保持时间（秒）"
    )
    session_missing_action: str | None = Field(
        default=None, pattern="^(RANDOM|REJECT|ROUND_ROBIN)$", description="会话缺失时的行为"
    )
    session_header_names: list[str] | None = Field(default=None, description="会话头字段名列表")
    session_query_param_names: list[str] | None = Field(
        default=None, description="会话查询参数名列表"
    )
    connect_session_header_names: list[str] | None = Field(
        default=None, description="CONNECT会话头字段名列表"
    )
    hop_pool_ids: list[int] | None = Field(default=None, description="跳跃代理池ID列表")


class HttpProxyEndpointServiceConfigRequest(BaseModel):
    """HTTP代理端点服务配置请求"""

    enabled: bool = Field(default=True, description="是否启用HTTP代理服务")
    health_check_enabled: bool = Field(default=True, description="是否启用健康检查")
    health_check_interval_sec: int = Field(
        default=30, ge=5, le=3600, description="健康检查间隔（秒）"
    )


class ChainInstanceCreateRequest(BaseModel):
    """创建链实例请求"""

    instance_id: str = Field(min_length=1, max_length=100, description="实例ID")
    front_node_key: str = Field(description="前端节点密钥")
    exit_node_key: str = Field(description="出口节点密钥")
    listen: str = Field(default="127.0.0.1", description="监听地址")
    port: int = Field(ge=1, le=65535, description="监听端口")
    inbound_type: str = Field(default="http", pattern="^(http|socks5)$", description="入站类型")


class StickyLeaseInheritRequest(BaseModel):
    """租约继承请求"""

    from_session_id: str = Field(description="源会话ID")
    to_session_id: str = Field(description="目标会话ID")


class PoolSessionRuleUpsertRequest(BaseModel):
    """更新池会话规则请求"""

    headers: list[str] = Field(default_factory=list, description="头字段名列表")


# ===== Wave 3.1: Inbound Port Management Schemas =====


class GatewayEndpointHealthResponse(BaseModel):
    """网关端点健康状态响应"""

    endpoint_id: int = Field(description="端点ID")
    name: str = Field(description="端点名称")
    listen_host: str = Field(description="监听地址")
    listen_port: int = Field(description="监听端口")
    enabled: bool = Field(description="是否启用")
    is_listening: bool = Field(description="是否正在监听")
    total_connections: int = Field(default=0, description="总连接数")
    active_connections: int = Field(default=0, description="活跃连接数")
    recent_errors: list[dict] = Field(default_factory=list, description="最近错误列表")
    active_leases: list[dict] = Field(default_factory=list, description="活跃租约列表")
    upstream_pool_status: dict = Field(default_factory=dict, description="上游池状态")
    last_health_check: str | None = Field(default=None, description="最后健康检查时间")
    health_check_enabled: bool = Field(default=True, description="健康检查是否启用")


class ConnectivityTestResponse(BaseModel):
    """连接测试响应"""

    endpoint_id: int = Field(description="端点ID")
    listen_host: str = Field(description="监听地址")
    listen_port: int = Field(description="监听端口")
    is_reachable: bool = Field(description="是否可达")
    latency_ms: int | None = Field(default=None, description="延迟（毫秒）")
    error: str | None = Field(default=None, description="错误信息")
    tested_at: str = Field(description="测试时间")
    connection_test: bool = Field(default=False, description="连接测试结果")
    http_test: bool = Field(default=False, description="HTTP测试结果")


class PortConflictItem(BaseModel):
    """端口冲突项"""

    port: int = Field(description="冲突端口")
    conflicting_sources: list[dict] = Field(default_factory=list, description="冲突来源列表")
    conflict_type: str = Field(
        description="冲突类型：endpoint_endpoint, endpoint_instance, instance_instance"
    )


class PortConflictResponse(BaseModel):
    """端口冲突检测响应"""

    has_conflicts: bool = Field(description="是否存在冲突")
    conflicts: list[PortConflictItem] = Field(default_factory=list, description="冲突列表")
    scanned_endpoints: int = Field(description="扫描的端点数")
    scanned_instances: int = Field(description="扫描的实例数")
    checked_at: str = Field(description="检查时间")


class PoolValidationIssue(BaseModel):
    """代理池验证问题"""

    field: str = Field(description="问题字段")
    issue_type: str = Field(description="问题类型：error, warning")
    message: str = Field(description="问题描述")
    suggestion: str | None = Field(default=None, description="修复建议")


class PoolValidationResponse(BaseModel):
    """代理池验证响应"""

    pool_id: int = Field(description="代理池ID")
    pool_name: str = Field(description="代理池名称")
    is_valid: bool = Field(description="配置是否有效")
    issues: list[PoolValidationIssue] = Field(default_factory=list, description="验证问题列表")
    validated_at: str = Field(description="验证时间")


class ConfigExportData(BaseModel):
    """配置导出数据"""

    version: str = Field(description="导出版本")
    exported_at: str = Field(description="导出时间")
    settings: dict = Field(default_factory=dict, description="系统设置")
    pools: list[dict] = Field(default_factory=list, description="代理池列表")
    endpoints: list[dict] = Field(default_factory=list, description="HTTP代理端点列表")
    subscriptions: list[dict] = Field(default_factory=list, description="订阅列表")
    chain_config: dict = Field(default_factory=dict, description="链式配置")
    gateway_config: dict = Field(default_factory=dict, description="网关配置")


class ConfigExportResponse(BaseModel):
    """配置导出响应"""

    data: ConfigExportData = Field(description="导出配置数据")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data": {
                        "version": "1.0",
                        "exported_at": "2026-05-28T12:00:00Z",
                        "settings": {
                            "test_url": "https://www.google.com",
                            "max_proxy_count": 50000,
                            "backend_health_check_sec": 60,
                            "max_failures_threshold": 3,
                        },
                        "pools": [
                            {
                                "id": 1,
                                "name": "默认代理池",
                                "filters": {"protocol": "http"},
                                "listen": "0.0.0.0:8080",
                                "inbound_type": "http",
                            }
                        ],
                        "endpoints": [
                            {
                                "id": 1,
                                "name": "HTTP端点",
                                "listen_host": "127.0.0.1",
                                "listen_port": 8899,
                            }
                        ],
                        "subscriptions": [
                            {
                                "id": 1,
                                "name": "示例订阅",
                                "url": "https://example.com/sub",
                                "enabled": True,
                            }
                        ],
                        "gateway_config": {"enabled": True, "health_check_enabled": True},
                        "chain_config": {},
                    }
                }
            ]
        }
    }


class ConfigImportRequest(BaseModel):
    """配置导入请求"""

    data: ConfigExportData = Field(description="要导入的配置数据")
    overwrite_existing: bool = Field(default=False, description="是否覆盖现有配置")
    import_settings: bool = Field(default=True, description="是否导入设置")
    import_pools: bool = Field(default=True, description="是否导入代理池")
    import_endpoints: bool = Field(default=True, description="是否导入HTTP代理端点")
    import_subscriptions: bool = Field(default=True, description="是否导入订阅")


class ConfigImportResponse(BaseModel):
    """配置导入响应"""

    success: bool = Field(description="是否成功")
    imported_items: dict = Field(default_factory=dict, description="导入的项目统计")
    errors: list[str] = Field(default_factory=list, description="导入错误列表")
    warnings: list[str] = Field(default_factory=list, description="导入警告列表")


# ===== Wave 4.3: System Health & Activity Schemas =====


class SystemHealthResponse(BaseModel):
    """系统健康状态响应"""

    backend_status: dict = Field(default_factory=dict, description="后端状态")
    gateway_status: dict = Field(default_factory=dict, description="网关状态")
    active_processes: int = Field(default=0, description="活跃进程数")
    pool_count: int = Field(default=0, description="代理池数量")
    proxy_count: int = Field(default=0, description="代理节点总数")
    healthy_proxy_rate: float = Field(default=0.0, description="健康代理比率（0-1）")
    uptime_seconds: int = Field(default=0, description="系统运行时间（秒）")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "backend_status": {"running": True, "pid": 12345, "routes": []},
                    "gateway_status": {"running": True, "items": []},
                    "active_processes": 2,
                    "pool_count": 3,
                    "proxy_count": 1500,
                    "healthy_proxy_rate": 0.856,
                    "uptime_seconds": 86400,
                }
            ]
        }
    }


class ActivityItem(BaseModel):
    """活动记录项"""

    id: int = Field(description="记录ID")
    timestamp: str = Field(description="时间戳")
    event_type: str = Field(description="事件类型")
    description: str = Field(description="事件描述")
    details: dict = Field(default_factory=dict, description="详细信息")


class SystemActivityResponse(BaseModel):
    """系统活动记录响应"""

    items: list[ActivityItem] = Field(default_factory=list, description="活动记录列表")
    total: int = Field(default=0, description="总记录数")


class PoolDependenciesResponse(BaseModel):
    """代理池依赖关系响应"""

    pool_id: int = Field(description="代理池ID")
    pool_name: str = Field(description="代理池名称")
    dependent_endpoints: list[dict] = Field(default_factory=list, description="依赖的HTTP代理端点")
    dependent_instances: list[dict] = Field(default_factory=list, description="依赖的链实例")
    has_dependencies: bool = Field(description="是否有依赖")


class PoolHealthSummaryResponse(BaseModel):
    """代理池健康摘要响应"""

    pool_id: int = Field(description="代理池ID")
    pool_name: str = Field(description="代理池名称")
    total_nodes: int = Field(default=0, description="总节点数")
    healthy_nodes: int = Field(default=0, description="健康节点数")
    degraded_nodes: int = Field(default=0, description="降级节点数")
    unavailable_nodes: int = Field(default=0, description="不可用节点数")
    healthy_rate: float = Field(default=0.0, description="健康率（0-1）")
    last_test_time: str | None = Field(default=None, description="最后测试时间")
    status: str = Field(description="整体状态：healthy/degraded/unhealthy")


# ===== Wave 5.4: Batch APIs & Pagination Schemas =====


class PoolBatchCreateRequest(BaseModel):
    """批量创建代理池请求"""

    pools: list[ProxyPoolCreateRequest] = Field(description="要创建的代理池列表")
    stop_on_error: bool = Field(default=False, description="遇到错误时是否停止")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pools": [
                        {
                            "name": "HTTP代理池",
                            "filters": {"protocol": "http", "available": "true"},
                            "listen": "0.0.0.0:8080",
                            "inbound_type": "http",
                        },
                        {
                            "name": "SOCKS5代理池",
                            "filters": {"protocol": "socks5"},
                            "listen": "0.0.0.0:1080",
                            "inbound_type": "socks5",
                        },
                    ],
                    "stop_on_error": False,
                }
            ]
        }
    }


class PoolBatchCreateResponse(BaseModel):
    """批量创建代理池响应"""

    created: int = Field(default=0, description="成功创建数量")
    failed: int = Field(default=0, description="失败数量")
    items: list[dict] = Field(default_factory=list, description="创建结果列表")
    errors: list[dict] = Field(default_factory=list, description="错误详情列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "created": 2,
                    "failed": 0,
                    "items": [
                        {"id": 1, "name": "HTTP代理池", "status": "created"},
                        {"id": 2, "name": "SOCKS5代理池", "status": "created"},
                    ],
                    "errors": [],
                }
            ]
        }
    }


class ProxyBatchTestRequest(BaseModel):
    """批量测试代理请求"""

    normalized_keys: list[str] = Field(description="要测试的代理密钥列表")
    concurrency: int = Field(default=50, ge=1, le=500, description="并发测试数")


class ProxyBatchTestResponse(BaseModel):
    """批量测试代理响应"""

    total: int = Field(description="总数")
    completed: int = Field(default=0, description="已完成数")
    success: int = Field(default=0, description="成功数")
    failed: int = Field(default=0, description="失败数")
    results: list[dict] = Field(default_factory=list, description="测试结果列表")


class SubscriptionBatchRefreshRequest(BaseModel):
    """批量刷新订阅请求"""

    subscription_ids: list[int] = Field(description="要刷新的订阅ID列表")
    timeout_sec: float = Field(default=30.0, ge=1.0, le=300.0, description="每个订阅的刷新超时时间")


class SubscriptionBatchRefreshResponse(BaseModel):
    """批量刷新订阅响应"""

    total: int = Field(description="总数")
    success: int = Field(default=0, description="成功数")
    failed: int = Field(default=0, description="失败数")
    results: list[dict] = Field(default_factory=list, description="刷新结果列表")


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1, description="页码")
    per_page: int = Field(default=20, ge=1, le=500, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel):
    """分页响应"""

    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    per_page: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    items: list = Field(description="数据列表")


# ===== Wave 6.3: Backend Monitoring Schemas =====


class ProcessInfo(BaseModel):
    """进程信息"""

    id: str = Field(description="进程ID（实例ID或backend）")
    pid: int = Field(description="操作系统进程ID")
    type: str = Field(description="进程类型：backend/instance")
    status: str = Field(description="进程状态：running/stopped/error")
    port: int | None = Field(default=None, description="监听端口")
    memory_mb: float | None = Field(default=None, description="内存使用（MB）")
    cpu_percent: float | None = Field(default=None, description="CPU使用率（%）")
    uptime_seconds: int | None = Field(default=None, description="运行时间（秒）")
    config_file: str | None = Field(default=None, description="配置文件路径")
    last_error: str | None = Field(default=None, description="最近错误")


class SystemProcessesResponse(BaseModel):
    """系统进程列表响应"""

    items: list[ProcessInfo] = Field(default_factory=list, description="进程列表")
    total: int = Field(default=0, description="总进程数")
    running: int = Field(default=0, description="运行中进程数")


class LogEntry(BaseModel):
    """日志条目"""

    timestamp: str = Field(description="时间戳")
    level: str = Field(description="日志级别：INFO/WARN/ERROR/DEBUG")
    source: str = Field(description="日志来源")
    message: str = Field(description="日志消息")


class SystemLogsResponse(BaseModel):
    """系统日志响应"""

    items: list[LogEntry] = Field(default_factory=list, description="日志列表")
    total: int = Field(default=0, description="总条数")
    level_filter: str | None = Field(default=None, description="级别过滤器")


class SystemResourcesResponse(BaseModel):
    """系统资源响应"""

    cpu: dict = Field(default_factory=dict, description="CPU使用情况")
    memory: dict = Field(default_factory=dict, description="内存使用情况")
    disk: dict = Field(default_factory=dict, description="磁盘使用情况")
    uptime_seconds: int = Field(default=0, description="系统运行时间")
    timestamp: str = Field(description="采集时间")


class ChainDiagnosticsResponse(BaseModel):
    """链式代理诊断响应"""

    status: str = Field(description="整体状态")
    front_pool: dict = Field(default_factory=dict, description="前置池状态")
    exit_pool: dict = Field(default_factory=dict, description="出口池状态")
    health_check: dict = Field(default_factory=dict, description="健康检查状态")
    active_leases: int = Field(default=0, description="活跃租约数")
    circuit_breakers: dict = Field(default_factory=dict, description="熔断器状态")
    routing_stats: dict = Field(default_factory=dict, description="路由统计")
    recent_errors: list[str] = Field(default_factory=list, description="最近错误列表")


# ===== Wave 7.4: Backend Health & Auto-Recovery Schemas =====


class SystemVersionResponse(BaseModel):
    """系统版本响应"""

    version: str = Field(description="系统版本号")
    python_version: str = Field(description="Python版本")
    platform: str = Field(description="运行平台")
    architecture: str = Field(description="系统架构")
    build_time: str | None = Field(default=None, description="构建时间")
    uptime_seconds: int = Field(description="系统运行时间（秒）")
    api_uptime_seconds: int = Field(description="API运行时间（秒）")


class ConfigDiffItem(BaseModel):
    """配置差异项"""

    key: str = Field(description="配置键名")
    stored_value: str | None = Field(default=None, description="存储的配置值")
    running_value: str | None = Field(default=None, description="运行中的配置值")
    status: str = Field(description="差异状态：added/removed/changed/unchanged")


class ConfigDiffResponse(BaseModel):
    """配置差异响应"""

    has_diff: bool = Field(description="是否存在配置差异")
    differences: list[ConfigDiffItem] = Field(default_factory=list, description="配置差异列表")
    stored_config_hash: str | None = Field(default=None, description="存储配置哈希")
    running_config_hash: str | None = Field(default=None, description="运行配置哈希")


class RollbackRequest(BaseModel):
    """配置回滚请求"""

    target_version: str | None = Field(
        default=None, description="目标版本，None表示回滚到上一个版本"
    )
    dry_run: bool = Field(default=False, description="试运行模式，不实际执行回滚")


class RollbackResponse(BaseModel):
    """配置回滚响应"""

    success: bool = Field(description="回滚是否成功")
    rolled_back_items: int = Field(description="回滚的配置项数量")
    previous_version: str | None = Field(default=None, description="回滚前的版本")
    message: str = Field(description="操作结果消息")


class ErrorCode(BaseModel):
    """错误码信息"""

    code: str = Field(description="错误码：ERR_XXX_XXX格式")
    message: str = Field(description="错误消息")
    suggestion: str | None = Field(default=None, description="修复建议")


class ErrorResponse(BaseModel):
    """标准错误响应"""

    detail: str = Field(description="错误信息")
    code: str = Field(description="错误码：ERR_XXX_XXX格式")
    field: str | None = Field(default=None, description="错误字段")
    suggestion: str | None = Field(default=None, description="修复建议")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "代理池名称 'test' 已存在",
                    "code": "ERR_POOL_NAME_DUP",
                    "field": "name",
                    "suggestion": "请使用其他名称",
                }
            ]
        }
    }


# Error code constants
class ErrorCodes:
    """错误码常量定义"""

    # Pool errors
    ERR_POOL_NOT_FOUND = "ERR_POOL_NOT_FOUND"
    ERR_POOL_NAME_DUP = "ERR_POOL_NAME_DUP"
    ERR_POOL_HAS_ENDPOINTS = "ERR_POOL_HAS_ENDPOINTS"
    ERR_POOL_HAS_INSTANCES = "ERR_POOL_HAS_INSTANCES"
    ERR_POOL_FILTERS_INVALID = "ERR_POOL_FILTERS_INVALID"

    # Endpoint errors
    ERR_ENDPOINT_NOT_FOUND = "ERR_ENDPOINT_NOT_FOUND"
    ERR_ENDPOINT_NAME_DUP = "ERR_ENDPOINT_NAME_DUP"
    ERR_PORT_CONFLICT = "ERR_PORT_CONFLICT"
    ERR_ENDPOINT_NO_HOPS = "ERR_ENDPOINT_NO_HOPS"

    # Proxy errors
    ERR_PROXY_NOT_FOUND = "ERR_PROXY_NOT_FOUND"
    ERR_PROXY_KEY_INVALID = "ERR_PROXY_KEY_INVALID"

    # Subscription errors
    ERR_SUBSCRIPTION_NOT_FOUND = "ERR_SUBSCRIPTION_NOT_FOUND"
    ERR_SUBSCRIPTION_URL_INVALID = "ERR_SUBSCRIPTION_URL_INVALID"

    # Config errors
    ERR_CONFIG_IMPORT_FAILED = "ERR_CONFIG_IMPORT_FAILED"
    ERR_CONFIG_ROLLBACK_FAILED = "ERR_CONFIG_ROLLBACK_FAILED"

    # Process errors
    ERR_PROCESS_NOT_FOUND = "ERR_PROCESS_NOT_FOUND"
    ERR_PROCESS_RESTART_FAILED = "ERR_PROCESS_RESTART_FAILED"

    # Backend errors
    ERR_BACKEND_NOT_RUNNING = "ERR_BACKEND_NOT_RUNNING"
    ERR_BACKEND_START_FAILED = "ERR_BACKEND_START_FAILED"

    # Metrics errors
    ERR_METRICS_NOT_AVAILABLE = "ERR_METRICS_NOT_AVAILABLE"
    ERR_METRICS_AGGREGATION_FAILED = "ERR_METRICS_AGGREGATION_FAILED"

    # System errors
    ERR_SYSTEM_INTERNAL = "ERR_SYSTEM_INTERNAL"
    ERR_SYSTEM_UNAVAILABLE = "ERR_SYSTEM_UNAVAILABLE"


def create_error_response(
    code: str,
    detail: str,
    field: str | None = None,
    suggestion: str | None = None,
) -> ErrorResponse:
    """创建标准错误响应"""
    return ErrorResponse(
        detail=detail,
        code=code,
        field=field,
        suggestion=suggestion,
    )


# ===== Wave 17.3: Performance Metrics Schemas =====


class LatencyPercentiles(BaseModel):
    """延迟百分位数"""

    p50: float = Field(default=0.0, description="50th percentile (median)")
    p90: float = Field(default=0.0, description="90th percentile")
    p95: float = Field(default=0.0, description="95th percentile")
    p99: float = Field(default=0.0, description="99th percentile")


class RequestMetrics(BaseModel):
    """请求指标"""

    total_requests: int = Field(default=0, description="总请求数")
    successful_requests: int = Field(default=0, description="成功请求数")
    failed_requests: int = Field(default=0, description="失败请求数")
    error_rate: float = Field(default=0.0, description="错误率 (0-1)")
    avg_latency_ms: float = Field(default=0.0, description="平均延迟 (ms)")
    latency_percentiles: LatencyPercentiles = Field(
        default_factory=LatencyPercentiles, description="延迟百分位数"
    )


class SystemMetricsResponse(BaseModel):
    """系统性能指标响应"""

    timestamp: str = Field(description="采集时间")
    uptime_seconds: int = Field(description="系统运行时间 (秒)")
    requests: RequestMetrics = Field(description="请求指标")
    active_connections: int = Field(default=0, description="活跃连接数")
    total_proxies_tested: int = Field(default=0, description="已测试代理总数")
    proxy_test_success_rate: float = Field(default=0.0, description="代理测试成功率 (0-1)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2026-05-28T12:00:00Z",
                    "uptime_seconds": 86400,
                    "requests": {
                        "total_requests": 15000,
                        "successful_requests": 14500,
                        "failed_requests": 500,
                        "error_rate": 0.033,
                        "avg_latency_ms": 45.2,
                        "latency_percentiles": {
                            "p50": 32.0,
                            "p90": 85.0,
                            "p95": 120.0,
                            "p99": 250.0,
                        },
                    },
                    "active_connections": 15,
                    "total_proxies_tested": 1200,
                    "proxy_test_success_rate": 0.85,
                }
            ]
        }
    }


class PoolMetricsResponse(BaseModel):
    """代理池性能指标响应"""

    pool_id: int = Field(description="代理池ID")
    pool_name: str = Field(description="代理池名称")
    timestamp: str = Field(description="采集时间")
    requests: RequestMetrics = Field(description="请求指标")
    active_proxies: int = Field(default=0, description="活跃代理数")
    total_proxies: int = Field(default=0, description="代理总数")
    healthy_proxies: int = Field(default=0, description="健康代理数")
    proxy_health_rate: float = Field(default=0.0, description="代理健康率 (0-1)")
    avg_latency_ms: float = Field(default=0.0, description="平均延迟 (ms)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pool_id": 1,
                    "pool_name": "HTTP代理池",
                    "timestamp": "2026-05-28T12:00:00Z",
                    "requests": {
                        "total_requests": 5000,
                        "successful_requests": 4800,
                        "failed_requests": 200,
                        "error_rate": 0.04,
                        "avg_latency_ms": 38.5,
                        "latency_percentiles": {
                            "p50": 28.0,
                            "p90": 65.0,
                            "p95": 95.0,
                            "p99": 180.0,
                        },
                    },
                    "active_proxies": 45,
                    "total_proxies": 50,
                    "healthy_proxies": 42,
                    "proxy_health_rate": 0.84,
                    "avg_latency_ms": 38.5,
                }
            ]
        }
    }


class MetricsWindow(BaseModel):
    """指标时间窗口"""

    window: str = Field(description="时间窗口：1min, 5min, 1hour")
    start_time: str = Field(description="窗口开始时间")
    end_time: str = Field(description="窗口结束时间")
    requests: RequestMetrics = Field(description="请求指标")


class MetricsExportResponse(BaseModel):
    """指标导出响应"""

    exported_at: str = Field(description="导出时间")
    system_metrics: SystemMetricsResponse = Field(description="系统指标")
    windows: list[MetricsWindow] = Field(default_factory=list, description="历史指标窗口")
    pools: list[PoolMetricsResponse] = Field(default_factory=list, description="代理池指标")


# ===== Wave 22.3: Monitoring Schemas =====


class RequestTraceResponse(BaseModel):
    """请求追踪响应"""

    correlation_id: str = Field(description="关联ID")
    path: str = Field(description="请求路径")
    method: str = Field(description="请求方法")
    duration_ms: float = Field(description="请求耗时（毫秒）")
    status_code: int = Field(description="HTTP状态码")
    client_ip: str = Field(default="", description="客户端IP")
    error: str = Field(default="", description="错误信息")
    response_size: int = Field(default=0, description="响应大小（字节）")
    start_time: str = Field(description="开始时间")


class ErrorSummaryResponse(BaseModel):
    """错误摘要响应"""

    total_errors: int = Field(default=0, description="总错误数")
    error_types: dict[str, int] = Field(default_factory=dict, description="错误类型统计")
    top_error_paths: list[dict] = Field(default_factory=list, description="错误最多的路径")
    error_rate_per_minute: float = Field(default=0.0, description="每分钟错误率")
    last_minutes: int = Field(default=60, description="统计时间范围（分钟）")


class BottleneckResponse(BaseModel):
    """性能瓶颈响应"""

    path: str = Field(description="请求路径")
    avg_latency_ms: float = Field(description="平均延迟（毫秒）")
    p95_latency_ms: float = Field(description="P95延迟（毫秒）")
    p99_latency_ms: float = Field(description="P99延迟（毫秒）")
    request_count: int = Field(description="请求次数")
    error_rate: float = Field(description="错误率")
    severity: str = Field(description="严重程度：normal/warning/critical")


class CapacityMetricsResponse(BaseModel):
    """容量规划指标响应"""

    total_requests: int = Field(default=0, description="总请求数")
    total_errors: int = Field(default=0, description="总错误数")
    error_rate: float = Field(default=0.0, description="错误率")
    top_paths: list[dict] = Field(default_factory=list, description="请求最多的路径")
    latency_stats: dict[str, dict] = Field(default_factory=dict, description="延迟统计")
    unique_paths: int = Field(default=0, description="唯一路径数")


class HealthSummaryResponse(BaseModel):
    """健康摘要响应"""

    active_requests: int = Field(default=0, description="活跃请求数")
    error_summary: ErrorSummaryResponse = Field(default_factory=ErrorSummaryResponse, description="错误摘要")
    bottlenecks: list[BottleneckResponse] = Field(default_factory=list, description="性能瓶颈列表")
    capacity: CapacityMetricsResponse = Field(default_factory=CapacityMetricsResponse, description="容量指标")
    timestamp: str = Field(description="采集时间")
