# Phase 2 实现说明

## 已完成

1. `Tester` 实现
- 文件: `proxypool/tester/singbox.py`, `proxypool/tester/service.py`
- 支持 sing-box 动态配置生成与子进程拨测
- 若 sing-box/curl 不可用，自动回退 TCP 连通探测
- 支持并发检测、结果回写、失败计数、失效淘汰

2. `API + WebUI` 实现
- 文件: `proxypool/api/app.py`, `proxypool/webui/index.html`
- API 提供: 健康检查、代理查询、统计、订阅导出、导入、测速、调度
- WebUI 提供: 节点列表、状态展示、导入 output、手动测速、复制订阅

3. `Scheduler` 实现
- 文件: `proxypool/scheduler/jobs.py`
- 使用 APScheduler 定时采集和定时测速

4. `Storage` 增强
- 文件: `proxypool/storage/sqlite.py`
- 新增字段: `fail_count`, `last_error`
- 新增接口: 过滤查询、测试候选拉取、结果回写、统计、订阅导出、失效清理

5. 远程源采集 + API 鉴权
- 文件: `proxypool/collector/fetcher.py`, `proxypool/api/security.py`
- Collector 新增 `collect_from_urls` 与 `collect_from_sources`
- 新增 `configs/sources.txt` 与脚本 `scripts/import_sources_file.py`
- API 新增 URL/混合源导入接口与可选 `X-API-Key` 写接口鉴权

6. sing-box 后端管理
- 文件: `proxypool/backend/singbox_manager.py`
- 支持配置多条路由：不同 `inbound_port` 对应不同出站代理 `proxy_key`
- 提供 `/api/backend/status|routes|start|stop|restart` 管理接口
- 默认后端环境变量：`PROXYPOOL_BACKEND_ENGINE=singbox`

## 下一步

- 接入远程订阅 URL 拉取（HTTP source fetch）
- 支持 sing-box 批量出站配置复用，降低每节点进程开销
- 增加导出格式转换（clash/sing-box/xray）
- 为 API 增加鉴权与限流
