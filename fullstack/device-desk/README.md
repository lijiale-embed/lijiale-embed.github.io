# 设备运行状态与异常工单管理平台（Device Desk）

个人全栈 MVP，结合嵌入式背景练习设备台账与异常处理。使用 AI 辅助实现；不是商业项目或工作经历。所有设备与读数都是模拟数据，无真实硬件连接、自动采样或自动告警。

## 环境、安装与启动

本次验证环境：Windows、Node.js 24.19.0。要求 Node.js 24.x，使用内置 `node:sqlite`（该版本运行时可能提示实验特性警告），无需另外安装数据库。依赖由 package-lock.json 锁定。

在此目录执行：

```powershell
npm ci
npm start -- --seed
```

访问 http://127.0.0.1:3000 。`--seed` 仅在设备表为空时写入 3 个模拟设备和 1 条模拟工单；普通 `npm start` 不会填入示例，适合空数据验证。重启不会清空数据；再次对空库使用 `--seed` 会重新写入示例。

PowerShell 可用 `npm.cmd` 代替 `npm`，避免执行策略限制。无需启动作品集 HTTP 服务即可使用本平台；导航中的作品集链接指向公开作品集，新修改发布前仍显示其旧版本。

配置示例（可选）：

```powershell
$env:PORT = '3001'
$env:DB_PATH = 'C:\temp\device-desk-demo.sqlite'
npm start -- --seed
```

默认数据库为本目录 `data/device-desk.sqlite`。路径相对服务启动目录解析；默认值按源码文件位置解析。数据库及日志不提交 Git。

## 操作路径

1. 查看设备列表，通过名称 / 编号与状态筛选。
2. 新增、查看、编辑、删除设备；前端原生表单校验、后端独立校验。
3. 为已有设备创建工单，填写标题、描述和优先级。
4. 点击“开始处理”，再“关闭工单”；查看详情中的创建、更新和关闭时间。
5. 已关联工单的设备禁止删除，包含已关闭工单；保留历史，不级联删除。
6. 停止服务后重启，确认数据保留。空列表有提示，服务断开后显示错误与刷新重试入口。

温度允许 -50–150 °C，湿度允许 0–100%，未采样可为 null。设备编号为唯一的 1–32 位字母、数字、下划线或连字符；名称最长 80 字。工单标题最长 120 字、描述最长 2000 字。状态仅允许 open → in_progress → closed，不可跳转、重复流转或重开。

## 架构与选型

```text
HTML 表单 / 列表 / 原生 dialog
        ↓ fetch + JSON / 同源 HTTP
Express 路由 → 字段校验 → 状态规则 → 参数化 SQL
        ↓                         ↓
统一错误结构                  SQLite 文件
        ↓                         ↓
前端提示 / 刷新              外键与唯一性约束
```

前端只负责展示、输入和请求；数据库和业务规则由服务端维护。使用 Express 避免手写路由与静态服务，SQLite 便于本地复现且能验证重启持久化，Node 内置测试工具减少测试依赖。使用同步 SQLite API，适合本地小规模练习，不承诺高并发能力。

数据模型：

| 表 | 字段与约束 |
| --- | --- |
| devices | id 主键；code 唯一；name；status；temperature / humidity 可为空；updated_at（UTC ISO 时间） |
| tickets | id 主键；device_id 外键；title；description；priority；status；created_at；updated_at；closed_at |

外键 RESTRICT 保护设备历史；状态和模拟读数有数据库 CHECK 约束，字段长度、工单状态迁移在应用层校验。关闭时间仅在成功关闭时写入。

## REST API

成功返回 `{ "data": ... }`，失败返回 `{ "error": { "code": "VALIDATION", "message": "..." } }`。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | /api/health | 健康检查，含 simulated: true |
| GET | /api/devices?q=&status= | 设备列表，按名称 / 编号与状态筛选 |
| POST | /api/devices | 创建设备，返回 201 |
| GET | /api/devices/:id | 设备详情 |
| PUT | /api/devices/:id | 全量更新设备字段 |
| DELETE | /api/devices/:id | 删除无工单设备 |
| GET | /api/tickets?q=&status=&device_id= | 工单列表，搜索标题 / 描述 / 设备编号 |
| POST | /api/tickets | 为已有设备创建待处理工单，返回 201 |
| GET | /api/tickets/:id | 工单详情及关联设备 |
| PATCH | /api/tickets/:id | 按状态机更新工单 |

创建设备示例：

```json
{ "code": "SIM-NEW-04", "name": "模拟采集器", "status": "online", "temperature": 25.5, "humidity": 50 }
```

创建工单：

```json
{ "device_id": 1, "title": "检查模拟读数", "description": "人工录入的练习异常", "priority": "high" }
```

状态更新：`{ "status": "in_progress" }`，之后 `{ "status": "closed" }`。
设备状态：online / offline / warning；优先级：low / medium / high。
错误码：400 字段或 JSON 非法；403 跨源写入；404 资源不存在；409 唯一编号冲突、关联工单或非法状态迁移；413 请求体超过 16 KB；415 非 JSON 写入；500 内部错误（详细原因仅输出服务日志）。

日志按请求输出 JSON，包含方法、路径、响应码和耗时，不记录表单正文。浏览器使用 textContent 构建动态内容，数据库查询使用占位参数。

## 自动化测试

```powershell
npm test
```

test/api.test.js 使用真实 HTTP 请求、独立数据库与临时端口，覆盖设备 CRUD、搜索筛选、输入边界、重复编号、工单流转、关联约束、错误协议和文件重开持久化。文件测试关闭连接后重开同一数据库，验证修改和关闭状态留存。完整测试与浏览器验收记录见作品集 verification/REPORT.md；源码包另附 docs/REPORT.md 与 API 原始输出。

## 目录

```text
app.js          Express 应用、数据库初始化、校验与 REST API
server.js       本地服务入口，环境变量与优雅关闭
public/         HTML / CSS / JavaScript 客户端
test/           Node 内置测试工具的 API 集成测试
package*.json   命令与锁定依赖
data/           运行时生成，Git 忽略
```

## 排查与边界

- EADDRINUSE：3000 端口被占用，可设置 PORT；不要结束不属于本项目的进程。
- Cannot find module / 缺少 node:sqlite：先确认 Node 24.x，再执行 npm ci。
- 页面报错或 API 无响应：检查 Node 日志和 /api/health，然后点击刷新。不能直接双击 HTML 或把 public 目录放到 GitHub Pages 来运行后端。
- 409：按错误说明更换设备编号、保留工单关联设备或遵循工单状态流转。
- 本项目仅绑定 127.0.0.1，无登录、权限、分页、自动采样、状态变更历史表或生产监控；列表全量读取，适用于小规模练习。
- GitHub Pages 只展示静态详情与截图；本平台未部署公网后端。未新增 Docker 配置，未验证容器或云平台部署。
- 作品集首页技能仅说明此个人练习的已验证技术，不代表已掌握生产全栈研发。
