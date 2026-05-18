# Web UI Module

## Scope

Web UI 是由 FastAPI 静态托管的单页管理台，用来操作 Proxy Pool 的端到端流程：导入节点、刷新订阅、运行检测任务、筛选节点、创建发布订阅、配置多跳代理池、管理 HTTP 网关、管理后端链路和查看进程记录。

## Key Files

- `proxypool/webui/package.json` 定义 Vite/Vue/Element Plus 前端依赖和 `dev`、`build`、`preview` 脚本。
- `proxypool/webui/vite.config.js` 配置 Vite、Vue 插件、生产输出目录和 `/api` 开发代理。
- `proxypool/webui/index.html` 是 Vite HTML 入口，只保留 `#app` 挂载点和 `src/main.js` 模块入口。
- `proxypool/webui/src/main.js` 创建 Vue 应用、注册 Element Plus、加载全局 CSS 并挂载 `App.vue`。
- `proxypool/webui/src/App.vue` 定义应用壳、侧边栏、全局消息、隐藏文件输入、代理 key datalist 和页面组件组合。
- `proxypool/webui/src/views/*.vue` 存放各主页面模板组件。
- `proxypool/webui/src/appOptions.js` 暂存迁移后的 root Options API 状态、计算属性和业务方法。
- `proxypool/webui/src/rootProxyMixin.js` 让页面组件复用 root 状态和方法，作为继续拆分业务逻辑前的兼容层。
- `proxypool/webui/src/styles/main.css` 定义控制台布局、表格、卡片、按钮、状态徽标和响应式样式。
- `proxypool/api/app.py` 服务 `proxypool/webui/dist/index.html` 和 `/assets/*`；直接由 FastAPI 提供 WebUI 前必须先运行 `npm run build`。

## Overall Layout

页面由 Vite 构建的 Vue 3 应用挂载在 `#app`。外层布局分为左侧 `sidebar` 和右侧 `workspace/main`。

`App.vue` 是根组件，负责应用壳和页面组合。页面级模板拆在 `src/views/` 下，当前仍通过 `rootProxyMixin` 访问 `appOptions.js` 中的 root 状态和方法。后续继续重构时，应把页面相关状态和方法逐步下沉到对应 view/composable，而不是继续扩大 `appOptions.js`。

左侧导航由 `activePage` 控制，包含 5 个主页面：

- `tasks`：任务中心。
- `subscriptions`：订阅管理。
- `published-subscriptions`：订阅发布。
- `proxy-pools`：多跳代理池工作区。
- `proxies`：代理节点表。

左侧底部显示全局状态摘要：节点总数、可用节点数、后端运行状态、任务数量。右侧顶部有全局消息条 `message`，用于显示操作成功或失败。

页面启动时，`mounted()` 会加载本地偏好和服务端状态，包括表格列配置、链路默认值、测速回退配置、测速筛选、任务并发、自动任务配置、后端端口范围、任务列表、代理列表、订阅、发布订阅、代理池、网关端点、后端状态和网关状态。

## Main Page: Tasks

`任务中心` 是常用运维操作入口，组件文件为 `src/views/TasksPage.vue`，显示条件为 `activePage === 'tasks'`。

页面布局：

- 顶部 `任务操作` 快捷操作卡片。
- 中部 `settings-grid` 配置区。
- 底部 `任务列表`，展示长任务进度。

快捷操作包括：

- `导入节点文件`：打开隐藏文件选择器，读取本地文件后调用 `/api/collector/import-texts`。
- `立即测速`：调用 `/api/tasks/tester/start`，按当前测速筛选、并发和回退前置代理配置启动批量测试。
- `测试网速`：调用 `/api/tasks/speed-test/start`。
- `检测ChatGPT解锁`：调用 `/api/tasks/openai-check/start`。
- `补全IP位置`：调用 `/api/tasks/geoip/start`。
- `检测IP纯净度`：调用 `/api/tasks/ip-purity/start`。
- `删除不可用`：调用 `/api/proxies/delete-unavailable`。
- `复制订阅`：读取 `/api/subscription?only_available=true` 并复制到剪贴板。
- `导出链接`：直接打开可用节点订阅地址。

配置区包含：

- `测速回退配置`：保存前置代理序号列表和最多尝试次数，供批量测速和单节点测试使用。
- `测速筛选`：配置测试全部、仅不可用、仅可用、仅未测速，以及复测间隔和失败时自动替换落地节点。
- `并发设置`：分别配置测速、解锁、GeoIP、IP 纯净度任务并发。
- `网速测试`：配置测速文件 URL、节点数量、超时时间和是否仅对可直连的节点测速；开启时排除依赖前置代理才可连通的链式节点。
- `自动任务`：配置自动刷新订阅、自动测速、自动网速测试及其间隔、限制和超时，通过 `/api/tasks/auto-config` 读写。

任务列表展示字段包括任务名称、状态、进度条、完成/总数、成功/失败、结果摘要和更新时间。运行中或排队任务可停止，已结束任务可删除记录。前端每 1.2 秒轮询 `/api/tasks?limit=80`，任务结束后自动刷新代理、代理目录和订阅列表。

## Main Page: Subscriptions

`订阅管理` 用于维护远程订阅源，组件文件为 `src/views/SubscriptionsPage.vue`，显示条件为 `activePage === 'subscriptions'`。

页面布局：

- 顶部按钮：刷新全部、删除不可用、刷新列表。
- 添加订阅表单：订阅名称、订阅链接 URL、添加按钮。
- 全局更新代理：保存一个可选代理序号，刷新订阅时可通过该代理拉取源内容。
- 订阅表格和分页。

订阅表格列包括：

- ID。
- 名称，可直接编辑。
- 链接，长 URL 会截断显示。
- 启用状态，可切换启用/停用。
- 上次刷新状态。
- 统计：解析、新增、更新、无效、去重。
- 上次刷新时间。
- 操作：刷新单个订阅、删除订阅。

主要 API：

- `GET /api/subscriptions?limit=1000`
- `POST /api/subscriptions`
- `PUT /api/subscriptions/{id}`
- `POST /api/subscriptions/{id}/refresh`
- `POST /api/tasks/subscriptions-refresh/start`
- `POST /api/subscriptions/delete-unavailable`
- `GET/PUT /api/subscription-update-proxy`

## Main Page: Published Subscriptions

`订阅发布` 用于创建对外导出的订阅视图，组件文件为 `src/views/PublishedSubscriptionsPage.vue`，显示条件为 `activePage === 'published-subscriptions'`。

页面布局：

- 顶部刷新按钮。
- `创建发布订阅` 表单。
- 发布订阅表格和分页。

创建表单支持配置：

- 名称。
- 发布格式：原始链接或 Clash YAML。
- 可用状态：仅可直连、仅不可直连、不限。
- ChatGPT 状态：已解锁、未解锁、未检测、不限。
- IP 纯净度：家宽、非家宽、未知、不限。
- 国家、城市。
- 链路：无前置、有前置、不限。
- 来源关键词。

表格列包括 ID、名称、格式、筛选条件、匹配节点数、启用状态和操作。操作支持套用当前筛选到表单、保存筛选、复制导出 URL、打开导出 URL、删除。

主要 API：

- `GET /api/published-subscriptions?limit=1000`
- `POST /api/published-subscriptions`
- `PUT /api/published-subscriptions/{id}`
- `DELETE /api/published-subscriptions/{id}`
- `GET /api/published-subscriptions/{id}/subscription`

## Main Page: Proxy Pools

`多跳代理池` 是链路和网关配置工作区，组件文件为 `src/views/ProxyPoolsPage.vue`，显示条件为 `activePage === 'proxy-pools'`。该页面内部由 `proxyPoolTab` 再分成 5 个子页面：

- `pools`：代理池。
- `gateway`：HTTP 网关。
- `chain`：链服务。
- `backend`：后端链路。
- `events`：进程记录。

切换到该主页面时，`selectPage()` 会加载代理池、网关端点、网关配置、网关状态、后端端口范围、默认监听、后端状态、链服务状态和健康状态。

### Proxy Pools Tab

`代理池` Tab 负责用户级代理池和池级链路配置。

创建代理池表单包含：

- 名称。
- 监听地址。
- 入站类型：HTTP 或 SOCKS。
- 链路类型：直连、链式、不可连接、不限。
- ChatGPT 状态。
- IP 纯净度。
- 国家多选。
- 延迟范围。
- 时效小时数。

代理池表格列包括 ID、名称、筛选条件、匹配节点数、状态和操作。操作支持同步、套用筛选、保存筛选、打开订阅源、删除。

池级链路配置用于选中某个代理池后配置：

- 是否启用池级链路。
- 粘性 TTL。
- 缺失会话动作：`RANDOM` 或 `REJECT`。
- HTTP 会话头列表。
- HTTP 会话 Query 列表。
- 统一网关路径前缀。

会话规则区支持按 URL 前缀定义额外会话头。表格可套用或删除已有规则。

池级路由测试区输入会话 ID 和目标域名，调用池级 route-test API，显示返回 JSON。

主要 API：

- `GET/POST /api/pools`
- `PUT/DELETE /api/pools/{id}`
- `POST /api/pools/{id}/sync`
- `GET/PUT /api/pools/{id}/chain`
- `GET/PUT/DELETE /api/pools/{id}/chain/session-rules/*`
- `GET /api/pools/{id}/chain/route-test`

### HTTP Gateway Tab

`HTTP 网关` Tab 负责配置可直接给客户端使用的 HTTP/HTTPS 代理入口。

页面分为三块：

- `HTTP 代理端点`：创建、编辑和管理多个端点。
- `统一 HTTP 网关`：兼容旧入口的默认接入配置。
- `接入方式` 和 `网关测试`：展示运行状态并执行连通性测试。

端点表单包含：

- 名称。
- 监听地址和监听端口。
- 是否启用。
- 多跳代理池顺序，支持上移/下移调整跳点顺序。
- 粘性 TTL。
- 缺失会话动作。
- HTTP 会话头。
- HTTP 会话 Query。
- CONNECT 会话头。

端点表格列包括 ID、名称、监听地址、跳点顺序、启用状态和操作。操作支持编辑、设为默认、测路由、删除。

统一 HTTP 网关表单包含启用状态、监听地址、监听端口、默认端点、缺失会话动作、HTTP 会话头、HTTP Query 和 CONNECT 会话头。

接入方式区展示默认 HTTP/HTTPS proxy 地址、所有端点地址、网关运行状态、租约数、实例数和端点监听数。网关测试区输入目标 URL、端点和会话 ID，调用测试 API 并显示返回 JSON。

主要 API：

- `GET/POST /api/http-proxy-endpoints`
- `GET/PUT/DELETE /api/http-proxy-endpoints/{id}`
- `GET /api/http-proxy-endpoints/{id}/route-test`
- `GET/PUT /api/gateway/http-config`
- `GET /api/gateway/http-status`
- `POST /api/gateway/http-test`

### Chain Service Tab

`链服务` Tab 负责前置/后置节点池和粘性租约状态。该功能当前未弃用，只是入口已从独立页面收敛到 `多跳代理池` 工作区内，与 `代理池`、`HTTP 网关`、`后端链路` 共用同一个配置页面。

顶部状态区显示：

- 服务状态。
- 前置节点健康数/总数。
- 后置节点健康数/总数。
- 健康检测运行状态。

配置区提供两个正则列表：

- 前置节点池正则。
- 后置节点池正则。

保存后会更新链服务池配置。按钮支持刷新状态、启动服务、停止服务。

`节点与租约` 内部还有 `chainNodeTab`：

- `front`：前置节点表，显示名称、协议、地址、健康/熔断、失败次数、延迟、出口 IP。
- `exit`：后置节点表，字段同前置节点。
- `leases`：粘性租约表，显示会话 ID、池 ID、出口节点、出口 IP、过期时间、最后访问。

租约操作支持刷新租约和清理过期租约。

主要 API：

- `GET /api/chain/status`
- `GET /api/chain/health`
- `POST /api/chain/start`
- `POST /api/chain/stop`
- `POST /api/chain/pools/{front|exit}`
- `GET /api/chain/leases`
- `POST /api/chain/leases/cleanup`

### Backend Chain Tab

`后端链路` Tab 负责 sing-box 后端、命名实例和链路路由配置。

`后端状态与实例管理` 显示：

- 当前后端类型。
- 是否运行。
- PID。
- 路由数量。

顶部按钮支持启动后端、停止后端、重启后端。实例管理表单通过实例 ID 创建、启动、停止、删除命名实例。实例表格显示实例、状态、PID、监听、端口、配置路径、错误和操作。

`sing-box 链路配置` 区用于编辑默认实例或指定实例的路由：

- 默认监听地址。
- 起始端口和结束端口。
- 网关 chain instances 的只读摘要表。
- 默认代理序号：前置、中间、落地，可应用到空白链路或全部链路。
- 按条件批量填充链路：按地区、ChatGPT 状态、家宽状态筛选代理，并填入前置/中间/落地列，或生成新链路。
- 链路表格：端口、类型、监听、前置代理、中间代理、落地代理、延迟、删除。
- 操作按钮：新增链路、保存配置、检测延迟。
- 高级 JSON 编辑：把 JSON 应用到表单或按 JSON 保存。

主要 API：

- `GET /api/backend/status`
- `POST /api/backend/start`
- `POST /api/backend/stop`
- `POST /api/backend/restart`
- `GET/POST /api/backend/instances`
- `POST /api/backend/instances/{id}/start`
- `POST /api/backend/instances/{id}/stop`
- `DELETE /api/backend/instances/{id}`
- `GET/POST /api/backend/instances/{id}/routes`
- `GET/POST /api/backend/routes`
- `GET/PUT /api/backend/default-port-range`
- `GET/PUT /api/backend/default-listen`
- `GET /api/backend/latency`

### Process Events Tab

`进程记录` Tab 展示后端进程事件表，来源是 backend manager 写入的 process events。

表格列包括：

- 时间。
- 动作。
- 结果。
- PID。
- 配置文件。
- 详情。

支持分页。数据来自 `/api/backend/process-events?limit=500`。

## Main Page: Proxies

`代理节点` 是节点库存表，组件文件为 `src/views/ProxiesPage.vue`，显示条件为 `activePage === 'proxies'`。

页面布局：

- 顶部操作：清空筛选、重置列、打开表格配置弹窗。
- 分页和批量操作：复制选中、删除选中、刷新、上一页、下一页。
- 表格配置弹窗。
- 代理节点表格。

表格配置弹窗同时管理筛选和列：

- 列顺序：上移/下移。
- 是否显示列。
- 自定义列名。
- 按列配置筛选条件。

支持的筛选包括：

- 协议。
- 状态。
- 最小带宽。
- 国家和城市。
- IP 纯净度。
- ChatGPT 解锁状态。
- 是否有可连通前置。
- 来源。

代理表格默认列包括：

- 序号。
- 协议。
- 地址。
- 延迟。
- 带宽 Mbps。
- 状态。
- 最后检测。
- IP 位置。
- IP 纯净度。
- ChatGPT 解锁。
- 可连通前置。
- 来源。
- 操作。

每行操作支持单节点测试和复制节点链接。批量操作支持复制选中节点链接和删除选中节点。

主要 API：

- `GET /api/proxies`
- `POST /api/tester/run-one`
- `POST /api/proxies/delete-selected`

## Shared UI State

核心状态字段：

- `activePage`：当前主页面。
- `proxyPoolTab`：多跳代理池内部 Tab。
- `chainNodeTab`：链服务里的节点/租约 Tab。
- `stats`, `proxies`, `allProxies`, `proxySerialMap`：节点数据和序号映射。
- `taskItems`, `taskPollingTimer`, `pendingTaskResultRefresh`：任务轮询和刷新。
- `subscriptions`, `publishedSubscriptions`, `proxyPools`, `gatewayEndpoints`：业务列表。
- `backendStatus`, `backendEvents`, `gatewayStatus`, `chainStatus`, `chainHealth`, `chainLeases`：运行态状态。
- `pagination`：每个表格独立分页状态。
- `buttonState`：按钮级 loading 状态。

## Local Storage Preferences

前端会把部分操作偏好保存在浏览器本地存储中，刷新页面后继续使用：

- 代理表格列顺序、列名和显示状态。
- 后端链路默认前置/中间/落地代理。
- 测速回退前置代理和尝试次数。
- 测速筛选条件。
- 各类任务并发。

这些偏好只影响当前浏览器，不会写入 SQLite；服务端配置仍通过 API 保存。

## API Interaction Pattern

同步操作通常直接 `fetch()` 对应 JSON API，成功后刷新相关列表。长任务通过 `startProgressTask()` 启动，服务端返回 `task_id` 后，前端轮询 `/api/tasks?limit=80` 展示进度。

开发时运行 `npm run dev` 启动 Vite，`/api` 会代理到 `http://127.0.0.1:8080`。生产或直接由 FastAPI 服务 WebUI 时，运行 `npm run build` 生成 `dist/`；FastAPI 会优先返回 `dist/index.html` 并挂载 `/assets/*`。

所有按钮操作统一包在 `runWithButtonState()` 中，避免重复点击并保持最短 loading 展示时间。错误通过 `setMessage(..., true)` 显示在全局消息条。

## Tests

模板和 UI/API 集成假设由以下测试覆盖：

- `tests/test_webui_template.py`
- `tests/test_webui_tasks.py`

更新页面结构、按钮文案、任务入口、API 路径、默认页面或本地存储 key 时，应同步更新本文档和相关测试。
