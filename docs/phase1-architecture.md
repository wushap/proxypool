# Proxy Pool 项目架构（第一阶段）

## 1. 项目目录结构

```text
proxypool/
├─ docs/
│  └─ phase1-architecture.md
├─ output/                         # 现有测试输入样本
├─ scripts/
│  └─ import_output_sources.py     # 第三阶段导入验证脚本
├─ proxypool/
│  ├─ __init__.py
│  ├─ models.py                    # ProxyNode 数据模型
│  ├─ collector/
│  │  ├─ __init__.py
│  │  ├─ parser.py                 # 多协议链接/订阅解析
│  │  └─ service.py                # 采集入库编排
│  └─ storage/
│     ├─ __init__.py
│     └─ sqlite.py                 # SQLite 存储与去重 Upsert
├─ tests/
│  ├─ test_parser.py
│  └─ test_collector.py
└─ requirements.txt
```

后续阶段会新增：
- `proxypool/tester/`（sing-box 子进程拨测、延迟统计）
- `proxypool/api/`（FastAPI 路由）
- `proxypool/webui/`（静态页面或 Vue 构建产物）
- `configs/`（sing-box 模板与运行时配置）

## 2. 三方依赖清单

见 `requirements.txt`，按职责分组：
- API 层：`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`
- 调度层：`APScheduler`
- 存储层：`SQLAlchemy`, `aiosqlite`
- 采集层：`httpx`, `PyYAML`, `aiofiles`
- 性能优化：`orjson`
- 轻量页面模板：`Jinja2`
- 测试：`pytest`

## 3. 模块数据流（文字图解）

### 3.1 Collector 数据流

1. Source Loader 读取本地文件/订阅 URL 文本。
2. Parser 按输入形态分流：
   - 单行分享链接（`vmess://`, `ss://`, `trojan://`, `vless://`, `hysteria2://` 等）
   - Base64 订阅（解码后再次提取链接）
   - Clash YAML（`proxies:` 列表）
3. 解析得到统一 `ProxyNode`。
4. Storage 执行 `normalized_key` 去重 Upsert。
5. 输出采集报告：`parsed/inserted/updated/invalid`。

### 3.2 Tester（后续阶段）数据流

1. 读取待检测节点（按 `last_checked_at`、失效次数等筛选）。
2. 批量生成 sing-box 临时配置（多 outbound）。
3. 启动 sing-box 本地 inbound（HTTP/SOCKS）并发拨测目标站点（Cloudflare/Google）。
4. 回写 `available/latency_ms/last_checked_at/fail_count`。
5. 对长期失效节点执行淘汰或降权。

### 3.3 API/WebUI（后续阶段）数据流

1. REST API 查询可用节点（按协议/延迟分页过滤）。
2. WebUI 拉取列表，展示协议、延迟、最后检测时间。
3. 导出接口生成订阅文本（原始链接或按目标格式转换）。
4. 前端支持“一键复制订阅”。

## 4. 关键设计约束

- 协议层统一字段：`protocol/host/port/name/extra/raw_link`，保证不同协议可共用存储与测试流程。
- 存储层以哈希键去重，避免同节点重复刷入。
- 解析与测试彻底解耦：Collector 只做“格式正确 + 元信息可提取”，连通性由 Tester 负责。
- sing-box 作为测试引擎默认方案，Xray-core 留作可插拔后端。
