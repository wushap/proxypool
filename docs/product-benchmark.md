# ProxyPool 产品化功能基准

> 基于竞品调研的代理池管理功能对标文档
> 
> 更新时间：2026-05-27

---

## 一、调研范围

调研了以下代理管理/代理池/代理网关产品的功能特性：

- **Clash 生态**：Clash Verge Rev、mihomo (Clash Meta)、Clash Dashboard
- **V2Ray 生态**：V2RayN、V2RayNG
- **代理池开源项目**：ProxyBroker、ProxyPool
- **代理后端**：sing-box、mihomo
- **企业级服务**：Bright Data、Oxylabs 等商业代理服务模式

---

## 二、功能基准清单

### P0: 必须有（产品可用性基础）

| 功能 | 描述 | 当前状态 | 备注 |
|------|------|:--------:|------|
| 多协议支持 | 支持主流代理协议（Trojan, VMess, SS, Hysteria2） | ✅ 已实现 | 核心竞争力 |
| 健康检查 | 自动定期检测代理可用性 | ✅ 已实现 | 后台定时任务 |
| 延迟测试 | 测量代理响应延迟 | ✅ 已实现 | 基于 TCP 握手 |
| 速度测试 | 测量代理带宽性能 | ✅ 已实现 | 基于下载测试 |
| RESTful API | 提供完整的代理管理 API | ✅ 已实现 | OpenAPI 文档 |
| API 认证 | API 密钥认证机制 | ✅ 已实现 | 支持环境变量配置 |
| WebUI 仪表板 | 可视化代理管理界面 | ✅ 已实现 | Vue 3.5 |
| 代理列表展示 | 显示代理节点列表及状态 | ✅ 已实现 | 支持排序和筛选 |
| Docker 部署 | 生产级容器化支持 | ✅ 已实现 | Docker Compose |
| SSRF 防护 | 服务器端请求伪造防护 | ✅ 已实现 | 安全边界 |
| 路径遍历防护 | 文件路径安全防护 | ✅ 已实现 | 安全边界 |
| 订阅源管理 | 支持从 URL 导入代理 | ✅ 已实现 | 支持批量导入 |

---

### P1: 用户期望（竞品标配）

| 功能 | 描述 | 当前状态 | 优先级 | 实现难度 |
|------|------|:--------:|:------:|:--------:|
| **代理分组管理** | 按用途、地区、协议等维度分组 | ❌ 未实现 | 高 | 中 |
| **代理标签系统** | 自定义标签便于检索和筛选 | ❌ 未实现 | 高 | 低 |
| **批量操作** | 批量测试、批量删除、批量导出 | ⚠️ 部分实现 | 高 | 中 |
| **代理排序** | 按延迟、成功率、最后使用时间排序 | ⚠️ 部分实现 | 高 | 低 |
| **实时流量统计** | 上传/下载速度和流量计数 | ❌ 未实现 | 中 | 中 |
| **日志过滤** | 按级别、时间、关键词过滤日志 | ❌ 未实现 | 中 | 低 |
| **连接成功率统计** | 长期成功率记录和展示 | ❌ 未实现 | 中 | 低 |
| **失败代理自动移除** | 连续失败 N 次自动标记/移除 | ⚠️ 部分实现 | 高 | 低 |
| **代理更新调度** | 定时更新订阅源 | ✅ 已实现 | - | - |
| **自动故障转移** | 主代理失效自动切换备用 | ✅ 已实现 | - | 链式路由 |
| **代理池自动补充** | 失效后自动从源补充新代理 | ⚠️ 部分实现 | 高 | 中 |

---

### P2: 差异化功能（竞争优势）

| 功能 | 描述 | 当前状态 | 优先级 | 实现难度 |
|------|------|:--------:|:------:|:--------:|
| **可视化图表** | 延迟分布、成功率趋势、带宽图表 | ❌ 未实现 | 中 | 中 |
| **地理定位路由** | 基于 GeoIP 选择代理 | ❌ 未实现 | 中 | 中 |
| **智能代理选择** | 基于综合评分的智能选择 | ❌ 未实现 | 中 | 高 |
| **告警通知** | 代理失效/性能下降通知 | ❌ 未实现 | 低 | 中 |
| **会话追踪** | 当前连接详情查看 | ❌ 未实现 | 低 | 高 |
| **连接详情** | 目标地址、协议、状态展示 | ❌ 未实现 | 低 | 高 |
| **主题定制** | UI 主题切换（深色/浅色） | ❌ 未实现 | 低 | 低 |
| **拖拽排序** | 代理节点拖拽排序 | ❌ 未实现 | 低 | 中 |
| **源评分系统** | 代理来源质量评分 | ❌ 未实现 | 低 | 中 |
| **配置脚本** | 用户自定义脚本支持 | ❌ 未实现 | 低 | 高 |

---

## 三、项目独有优势

### 1. 链式路由（Chain Routing）

**独特价值**：多跳代理链支持会话持久化

- 竞品对比：Clash/mihomo 仅支持单跳或简单故障转移，不支持真正的多跳链路
- 技术实现：通过 BackendManager 的链式组合实现
- 使用场景：高匿名需求、跨地域访问、规避地域封锁
- **这是我们的核心差异化优势**

### 2. 协议兼容性检查与降级

**独特价值**：自动检测协议兼容性并智能降级

- 竞品对比：大多数工具需要用户手动配置兼容协议
- 技术实现：ProtocolCompatibilityChecker 模块
- 使用场景：混合协议部署、渐进式升级
- **降低用户配置门槛**

### 3. 多后端引擎支持

**独特价值**：同时支持 sing-box 和 mihomo 两个主流后端

- 竞品对比：大部分工具仅支持单一后端
- 技术实现：BackendManager 抽象层 + EngineManager 管理
- 使用场景：根据需求选择最优后端、故障时切换
- **提供灵活性和容灾能力**

### 4. 生产级 Python 后端

**独特价值**：易于扩展和定制，API 文档完善

- 竞品对比：Go/C++ 实现的学习曲线更陡
- 技术实现：FastAPI + OpenAPI 自动生成
- 使用场景：企业集成、二次开发、快速原型
- **降低开发者门槛**

---

## 四、低成本可补齐功能（P1）详细分析

### 代码架构洞察

审查代码后发现项目已有良好的基础设施：

**已有基础设施**：
- ✅ SlidingWindow 统计系统（`proxypool/pool/scoring.py`）
- ✅ NodeScorer 评分模块
- ✅ APScheduler 定时任务调度（`proxypool/scheduler/jobs.py`）
- ✅ ProxyNode 模型已有 `fail_count`, `country`, `city` 字段
- ✅ API 已有 `sort_by` 和 `sort_order` 参数
- ✅ 前端 FilterPanel 组件已存在
- ✅ SQLite 数据库迁移简单

---

### 1. 代理排序增强 ⭐️ 首选

**价值**：中高 - 用户经常需要按性能排序

**实现难度**：极低

**现状**：API 已支持 `sort_by` 参数，但后端只支持 `latency` 和 `speed`

**改动范围**：
- `proxypool/storage/sqlite.py`：扩展 `list_proxies_filtered` 的排序选项
- `webui/src/composables/useProxyFilters.js`：添加排序状态
- `webui/src/views/ProxiesPage.vue`：添加排序下拉菜单

**新增排序字段**：
- `success_rate` - 成功率（已有 SlidingWindow 数据）
- `last_checked` - 最后检查时间
- `fail_count` - 失败次数（升序 = 最可靠优先）

**工作量预估**：0.5-1 天

**风险**：极低 - 只是添加排序字段

---

### 2. 失败代理自动清理 ⭐️ 首选

**价值**：高 - 自动化运维，减少人工干预

**实现难度**：低

**现状**：ProxyNode 已有 `fail_count` 字段，SchedulerService 已有定时任务

**改动范围**：
- `proxypool/scheduler/jobs.py`：添加 `cleanup-job` 定时任务
- `proxypool/storage/sqlite.py`：添加 `mark_unavailable()` 方法
- `proxypool/settings.py`：添加 `MAX_FAILURES` 配置项

**逻辑**：
```python
# 每 30 分钟检查一次
if fail_count >= MAX_FAILURES:  # 默认 5
    status = NodeStatus.UNAVAILABLE
    available = False
```

**工作量预估**：0.5 天

**风险**：极低 - 直接复用现有架构

---

### 3. 连接成功率统计 ⭐️ 首选

**价值**：高 - 用户需要知道代理可靠性

**实现难度**：低

**现状**：SlidingWindow 已经在内存中维护成功率数据，但未持久化和展示

**改动范围**：
- `proxypool/storage/sqlite.py`：添加 `success_count`, `total_checks` 字段
- `proxypool/pool/scoring.py`：在 NodeScorer.record() 中累加计数
- `proxypool/api/routers/proxies.py`：返回 `success_rate` 字段
- `webui/src/views/ProxiesPage.vue`：显示成功率百分比

**计算逻辑**：
```python
success_rate = success_count / total_checks * 100  # 百分比
```

**工作量预估**：1 天

**风险**：低 - 需要数据库迁移（添加 2 列）

---

### 4. 代理标签系统 ⭐️ 推荐

**价值**：高 - 用户刚需，便于管理大量代理

**实现难度**：低

**改动范围**：
- `proxypool/models.py`：添加 `tags: list[str]` 字段
- `proxypool/storage/sqlite.py`：添加 `tags_json TEXT` 列 + 索引
- `proxypool/api/routers/proxies.py`：扩展过滤参数支持 `tag`
- `webui/src/views/ProxiesPage.vue`：添加标签输入和筛选 UI

**工作量预估**：1-1.5 天

**风险**：低 - SQLite 添加列简单，无数据迁移

---

### 5. 日志过滤功能

**价值**：中 - 调试和监控时有用

**实现难度**：低

**改动范围**：
- `proxypool/api/routers/`：添加 `/api/logs` 端点（如果不存在）
- 日志存储：使用 RingBuffer 或最近 N 条日志
- API 参数：`level`, `since`, `keyword`, `limit`
- WebUI：在 TasksPage 添加日志过滤 UI

**工作量预估**：0.5-1 天

**风险**：低

---

### 6. 批量操作增强

**价值**：中 - 管理大量代理时需要

**实现难度**：中

**改动范围**：
- API：添加 `/api/proxies/batch` 批量端点
- 支持批量：测试、删除、标记状态、添加标签
- WebUI：添加多选复选框 + 批量操作工具栏

**工作量预估**：1-2 天

**风险**：中 - 需要注意并发和性能

---

### 推荐实施顺序

#### 第一阶段：核心价值（2-3 天）
1. **代理排序增强**（0.5-1 天）- 最低成本，立即可用
2. **失败代理自动清理**（0.5 天）- 自动化运维
3. **连接成功率统计**（1 天）- 核心指标展示

#### 第二阶段：用户体验（1.5-2 天）
4. **代理标签系统**（1-1.5 天）- 管理大量代理的刚需
5. **日志过滤功能**（0.5-1 天）- 调试便利性

#### 第三阶段：批量操作（1-2 天，可后续实现）
6. **批量操作增强**（1-2 天）- 视用户量决定

---

### 功能对比总结

| 功能 | 工作量 | 价值 | 复用度 | 推荐 |
|------|--------|------|--------|------|
| 排序增强 | 0.5-1天 | 高 | 高 | ✅ 首选 |
| 自动清理 | 0.5天 | 高 | 高 | ✅ 首选 |
| 成功率统计 | 1天 | 高 | 中 | ✅ 首选 |
| 标签系统 | 1-1.5天 | 高 | 中 | ✅ 推荐 |
| 日志过滤 | 0.5-1天 | 中 | 高 | ⚠️ 可选 |
| 批量操作 | 1-2天 | 中 | 中 | ⚠️ 可选 |

**核心结论**：
- 前 4 个功能（排序、清理、成功率、标签）可以在 3-4 天内完成
- 这些功能复用现有架构，改动小、风险低
- 完成后可以显著提升产品竞争力

---

### 技术实现要点

#### 数据库迁移策略
```sql
-- 添加标签
ALTER TABLE proxies ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]';

-- 添加成功率统计
ALTER TABLE proxies ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE proxies ADD COLUMN total_checks INTEGER NOT NULL DEFAULT 0;
```

#### API 扩展示例
```python
# 排序扩展
sort_by: str = Query(
    default="latency",
    pattern="^(latency|speed|success_rate|fail_count|last_checked)$"
)

# 标签过滤
tag: str | None = Query(default=None)
```

#### 前端组件复用
- FilterPanel -> ProxyFilters composable
- PaginationBar -> 分页逻辑
- TaskProgress -> 测试进度显示

---

## 五、功能对比矩阵

| 功能类别 | ProxyPool | Clash/mihomo | V2RayN | 商业服务 |
|---------|:---------:|:------------:|:------:|:--------:|
| 多协议支持 | ✅ | ✅ | ✅ | ✅ |
| 健康检查 | ✅ | ⚠️ API | ⚠️ 基础 | ✅ |
| 延迟/速度测试 | ✅ | ✅ | ✅ | ✅ |
| 链式路由 | ✅ | ❌ | ❌ | ⚠️ |
| 协议兼容检查 | ✅ | ❌ | ❌ | ❌ |
| WebUI | ✅ Vue 3 | ✅ Dashboard | ✅ GUI | ✅ |
| REST API | ✅ OpenAPI | ✅ | ⚠️ | ✅ |
| Docker | ✅ | ⚠️ | ❌ | ✅ |
| 代理轮换 | ⚠️ | ⚠️ | ⚠️ | ✅ |
| 地理定位 | ❌ | ✅ GeoIP | ⚠️ | ✅ |
| 可视化图表 | ❌ | ⚠️ | ⚠️ | ✅ |
| 告警通知 | ❌ | ❌ | ❌ | ✅ |
| 代理分组 | ❌ | ✅ | ⚠️ | ✅ |
| 日志过滤 | ❌ | ✅ | ✅ | ✅ |
| 批量操作 | ⚠️ | ✅ | ✅ | ✅ |

**图例**：✅ 完整支持 | ⚠️ 部分支持 | ❌ 不支持

---

## 六、竞品功能来源

- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev) - 现代代理客户端
- [mihomo APIs](https://wiki.metacubex.one/en/api/) - 代理引擎 API 文档
- [ProxyBroker](https://github.com/constverum/ProxyBroker) - 代理发现和验证
- [ProxyPool Software](https://grokipedia.com/page/Proxy_Pool_software) - 代理池软件对标
- [ScrapingAnt](https://scrapingant.com/blog/top-open-source-proxy-scrapers) - 代理抓取工具对比

---

## 七、建议实施路线

### 第一阶段：核心体验补齐（1-2 周）

1. 代理标签系统
2. 代理排序增强
3. 日志过滤功能
4. 连接成功率统计
5. 失败代理自动清理

### 第二阶段：可视化增强（2-3 周）

1. 延迟分布图表
2. 成功率趋势图表
3. 带宽使用图表
4. 代理健康度仪表板

### 第三阶段：智能功能（3-4 周）

1. 地理定位路由
2. 智能代理选择算法
3. 告警通知系统（邮件/Webhook）
4. 会话追踪和连接详情

---

**结论**：ProxyPool 在核心代理管理、链式路由、协议兼容检查等方面具有独特优势。建议优先补齐 P1 低成本功能（排序、清理、成功率、标签），快速提升产品竞争力。总计工作量约 3-4 天，可显著提升产品可用性。
