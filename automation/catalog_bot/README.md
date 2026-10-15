# 电商商品批量录入与校验机器人

业务痛点：运营逐条录入名称、SKU、售价与库存，重复输入、格式错误与失败重试难以追踪。
本项目使用虚构 Excel、真实本地网页和实际 Playwright 操作。不是商业后台自动化。

## 实现与边界

- server.py：Python HTTP 后台 + SQLite，SKU 为主键；同时保留后端字段校验。
- index.html：JavaScript 表单提交及商品列表，使用 textContent 展示内容，避免把输入解释为 HTML。
- robot.py：Excel → 校验 → Edge 标签定位 → 填表 → 点击 → 等待响应 → 列表核对 → 结果报表。
- 重复 SKU：批内完全重复跳过；后台同内容跳过，冲突则失败，不覆盖已有记录。
- 503 与超时最大重试 2 次；失败截图、逐行原因和尝试次数写入结果。
- 失联/批次中断写入 failed 状态，已有处理记录留存。进程或浏览器崩溃不保证可取得错误截图。

固定演示需要执行上级 run_demo.py。它开启 test-mode，预置 PRE001 并注入三个故障场景。
普通 server.py 不启用故障。这种显式故障注入用于测试，不是对实际业务故障率的观测。

## 实际结果

10 行：created 3、duplicate_input 1、duplicate_existing 1、invalid 3、failed 2。
RETRY-001 第二次成功；FAIL-001 与 SLOW-001 三次尝试后失败并截图。
重复执行后新增 0，数据库仍为 4 条（含 1 条预置商品）。
outputs/批量执行结果.xlsx、results.json、metrics.json、screenshots 提供实际证据。
端到端测试真实启动 HTTP 后台并驱动 Edge，不用接口调用替代机器人表单录入。

## 后续迁移影刀

按页面字段标签捕获元素，以 Excel 循环驱动输入与下拉选择，读取 message 反馈并核对 SKU 列表。
保留 Python 数据校验模块，异常时截图、记录行号、有限重试并转人工。
本次未搭建影刀客户端流程，不宣称影刀经验。生产还需权限、凭据管理、部署和业务验收。
