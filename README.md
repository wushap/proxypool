# Proxy Pool

基于 `Python + FastAPI + SQLite + sing-box` 的轻量代理池。

## 已实现模块

- `Collector`：多协议链接解析、Base64 订阅解析、Clash YAML 解析、去重入库
- `Collector`：支持本地文件 + 远程 URL + 混合 source 列表采集
- `Tester`：基于 `sing-box` 本地 socks inbound 的拨测（若缺少 sing-box 自动退化 TCP 连通）
- `Backend Manager`：支持多个入站端口映射到不同出站代理（默认后端 `singbox`）
- `Storage`：SQLite 持久化、状态回写、统计与订阅导出
- `API`：代理查询、导入、测速、订阅导出、调度开关
- `GeoIP`：补全节点 IP 与地理位置（国家/城市）
- `API Security`：可选 `X-API-Key` 鉴权（读接口放行，写接口鉴权）
- `WebUI`：列表展示、手动导入、手动测速、一键复制订阅
- `Task Progress`：补全IP、测速任务支持实时进度查询与前端进度条
- `Scheduler`：定时采集 + 定时测速

## 目录

- `proxypool/collector/`
- `proxypool/tester/`
- `proxypool/storage/`
- `proxypool/api/`
- `proxypool/webui/index.html`
- `scripts/import_output_sources.py`
- `scripts/import_sources_file.py`
- `scripts/run_once_tester.py`

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 快速开始

1. 导入 `output/` 样本：

```bash
python3 scripts/import_output_sources.py
```

2. 启动 API + WebUI：

```bash
python3 -m proxypool.main
```

打开：`http://127.0.0.1:8080/`

3. 手动跑一轮测速：

```bash
python3 scripts/run_once_tester.py
```

4. 按 `configs/sources.txt` 一键采集（支持 URL + 本地混合）：

```bash
python3 scripts/import_sources_file.py
```

## 配置环境变量

```bash
# 默认后端（不设置时即 singbox）
export PROXYPOOL_BACKEND_ENGINE='singbox'

# 可选：保护写接口（POST /api/*）
export PROXYPOOL_API_KEY='your-secret-key'

# 可选：自定义 sources 文件
export PROXYPOOL_SOURCES_FILE='/path/to/sources.txt'
```

当设置了 `PROXYPOOL_API_KEY`，调用写接口需带请求头：

```http
X-API-Key: your-secret-key
```

## API 速览

- `GET /api/health`
- `GET /api/stats`
- `GET /api/backend/status`
- `GET /api/backend/routes`
- `GET /api/proxies?limit=200&available=true`
- `GET /api/subscription?only_available=true&encode_base64=false`
- `POST /api/geoip/enrich`
- `POST /api/tasks/geoip/start`
- `POST /api/tasks/tester/start`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/collector/import-output`
- `POST /api/collector/import-urls`
- `POST /api/collector/import-sources`
- `POST /api/collector/import-sources-file`
- `POST /api/collector/import-files`
- `POST /api/backend/routes`
- `POST /api/backend/start`
- `POST /api/backend/stop`
- `POST /api/backend/restart`
- `POST /api/tester/run`
- `POST /api/scheduler/start`
- `POST /api/scheduler/stop`

## 测试

```bash
python3 -m unittest discover -s tests -v
```
