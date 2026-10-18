# 本次验收记录

验收日期：2026-10-18（Asia/Shanghai）。本次修改仅在本地，未提交、推送或发布。

## 实际运行结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 新增平台 Node HTTP API 测试 | 6 组通过、0 失败 | api-tests.txt、平台 test/api.test.js |
| 完整源码包独立复现 | 临时目录解压后 npm ci 成功、6 组 API 测试通过 | source-reproduction.txt |
| 原自动化项目 pytest | 17 通过、0 失败，含真实 Edge 端到端机器人 | python-tests.xml |
| 网站响应式 | 7 页 × 1440 / 768 / 390 px，共 21 项通过 | browser-results.json、home-*.png |
| 平台响应式 | 1440 / 768 / 390 px，无页面横向溢出 | app-*.png |
| 浏览器业务操作 | 14 项通过 | browser-results.json |
| 本地链接与资源 | 131 个链接引用、34 个独立资源，路径、锚点和 HTTP 读取通过 | browser-results.json |
| 外部 GitHub 链接 | 7 / 7 返回 HTTP 200 | browser-results.json |
| JavaScript 未处理错误 / 网站 HTTP 错误 | 0 / 0 | browser-results.json |
| 源码 ZIP 与既有 Excel 下载 | 浏览器实际触发并核对文件名 | verification/check.py |
| 网站入口清理 | 7 个页面与 CSS 无旧下载入口；4 份公开文档副本已移除 | verification/check.py、Git 差异 |

6 组 API 集成测试涵盖设备增删改查、搜索筛选、字段边界、唯一编号、工单关联、合法状态迁移、非法迁移拒绝、文件关闭再打开持久化、跨源写入、畸形 JSON、请求体大小、Content-Type 及 404。

14 项浏览器业务检查涵盖真实设备表单增查改删、搜索空结果、前端必填校验、Escape 关闭详情、工单创建与详情、完整流转与筛选、关联设备删除保护、用户内容按文本呈现、实际服务进程重启后工单保留、接口中断与恢复、真实空库首启、ZIP / Excel 下载、键盘跳至正文、导航与返回顶部。预期的 409 和断网错误由页面处理并显示，没有当作成功响应。

## 发现并修复的问题

- 原 Python 测试在 Windows 默认 GBK 环境读取包含中文错误信息的 UTF-8 JSON 时失败。两处读取改为显式 encoding='utf-8'；全套复测 17 项通过。原业务处理逻辑未改动，下载源码包同步修复。
- 作品集首屏重新定位为“技术开发实习作品集”，新平台放在首位，STM32 排在导盲车之前，保留原项目图片与仓库链接。
- 全栈项目卡片的长截图会拉高桌面卡片，已改为独立定位的裁切预览；详情页继续显示完整真实截图。
- 原始交付文档保留在仓库外 deliverables，本次仅删除网站 downloads 中的同字节副本。未创建新求职文档。

## 复现检查

本报告的本地运行证据在发布前审查中重新核对。原报告未逐项列出完整执行命令，补充如下；最新复测结果与静态检查边界见 PREPUBLISH_REVIEW.md。

最终审查补充修复了图标缺失产生的控制台 404、外链失败未触发断言及测试 XML 的主机名元数据。修复后已重新验证网页、外链、子目录刷新和源码包。业务 API 6 组、Python 17 项均在隔离副本中实际通过；本次无远程发布动作。

| 工作目录 | 实际命令 | 覆盖范围 |
| --- | --- | --- |
| fullstack/device-desk | npm.cmd test（脚本为 node --test test/*.test.js） | 真实本地 HTTP API，不是线上服务 |
| automation | Python 环境中的 python -m pytest tests -v --junitxml=<隔离输出文件> | 数据处理、校验、真实 Edge 机器人 |
| 仓库根目录 | python verification/check.py | 静态站 HTTP 资源和真实 Edge 页面、独立本地 Node 服务 |
| 源码包解压后的 device-desk | npm.cmd ci --no-audit --no-fund；npm.cmd test | 干净安装与 API 测试，非部署 |
| 仓库根目录 | git status --short；git diff --stat；git diff --check | Git 范围和空白错误静态检查 |

源码、安全文件和旧入口检查属于静态检查；移动端结果是 Edge 模拟视口，不是真实手机实测。全站没有 build 脚本，纯静态首页不需要 npm 构建。

在 fullstack/device-desk 执行 npm ci、npm test。环境为 Node.js 24.19.0；依赖由 package-lock.json 锁定。
浏览器检查：在仓库根目录，安装 Python playwright 且已安装 Edge 后执行 python verification/check.py。
脚本使用临时端口和独立数据库，结束时关闭自行创建的进程；不会清空默认业务数据库。
源码包：python verification/package_source.py，排除 node_modules、数据库和日志，包含源码、测试、锁文件、README 与本次测试记录。

## 修改文件范围

- 修改 index.html、styles.css、README.md、.gitignore 与原有 5 个 projects/*.html。
- 修改 automation/tests/test_automation.py 的两处 UTF-8 读取，同步 downloads/automation-source.zip。
- 新增 projects/device-desk.html、assets/device-desk.png、downloads/device-desk-source.zip。
- 新增 fullstack/device-desk/ 的服务端、前端、package.json / lockfile、README 和 test/api.test.js。
- 新增 verification/ 的检查脚本、源码打包脚本、报告、真实测试输出和截图。
- 删除 downloads 中原有 4 份公开文档副本，原始 deliverables 文件未改动。

## 发布与未验证范围

网站保持无需构建的静态 GitHub Pages：从 main / 根目录发布，保留 .nojekyll。预览执行 python -m http.server 8766 --bind 127.0.0.1。
平台单独 npm start -- --seed，仅绑定 127.0.0.1:3000。GitHub Pages 展示项目详情和截图，不提供在线后端；所有设备读数均是人工维护的模拟值。

尚未实现：平台登录 / 权限、分页、自动采样、自动告警、实时推送和状态变更历史表。未进行并发性能、真实硬件接入、Docker 或云部署验证。既有 ESP32 项目未重新编译和实物运行；STM32 / 导盲车现有资料缺少完整固件，保留对应说明，不宣称可直接编译复现。
