# Python 业务自动化作品集

两个 AI 辅助开发的个人模拟业务项目，所有商品、订单、退款均为虚构。不是 beU 商业系统，不声称影刀实操经验。
本目录包含共享工具、两个项目、测试与真实运行证据；建议整体下载，单独复制子目录会缺少 shared.py。

## 环境与一键验收

支持 Windows 10/11、Python 3.12、已安装 Microsoft Edge。Playwright 直接使用 Edge，无需下载额外浏览器。
在本目录执行（无需激活 PowerShell 脚本）：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe make_samples.py
./.venv/Scripts/python.exe run_demo.py
./.venv/Scripts/python.exe -m pytest tests -v --junitxml=evidence/pytest.xml
```

run_demo.py 自动启动临时本地后台，真实驱动 Edge 执行两轮商品录入，保留截图与结果，再关闭该后台。
每次使用新 SQLite 文件，已有文件不会被清空。测试使用独立临时目录，不污染演示状态。

单独运行日报：

```powershell
./.venv/Scripts/python.exe ops_daily/pipeline.py --date 2026-10-15
```

手动查看普通商品后台，在一个终端运行：

```powershell
./.venv/Scripts/python.exe catalog_bot/server.py
```

浏览器打开 http://127.0.0.1:8877 。另开终端运行真实机器人：

```powershell
./.venv/Scripts/python.exe catalog_bot/robot.py --headed
```

普通模式不注入故障，RETRY/FAIL/SLOW 名称只是普通 SKU，结果会与测试模式不同。
请用 run_demo.py 复现故障演示与文档中的固定测试结果。它会预置 PRE001，再开启 test-mode。

## 交付与证据

- ops_daily：Python 日报处理、混合 CSV/XLSX 输入、实际运营日报与异常 JSON。
- catalog_bot：本地商品管理页面、SQLite 后台、Playwright 机器人、逐行结果 Excel、真实成功/错误截图。
- tests：业务边界与真实浏览器端到端测试。
- evidence：pytest.xml、测试报告.md、demo_metrics.json，均由实际运行生成。
- ../assets/ops-flow.svg、catalog-flow.svg：流程图；../projects/：中文详情页及截图。

单次运行耗时与测试结果见 evidence/测试报告.md。没有人工基线，不宣称效率提升百分比。
requirements.txt 固定了本次验收环境，包安装版本以该文件为准。

## 日志、重跑与维护

- 业务错误进入异常明细，文件结构错误立即失败；检查 metrics.json 的状态后再使用报表。
- 结果报表使用临时文件后原子替换；同一输出目录不要并发运行两个批次。
- 机器人对暂时错误最多重试 2 次；SKU 唯一约束与相同内容检查避免重复写入。
- 失败截图包含当前商品表单和本地虚构商品，不处理真实客户资料。
- Excel 被占用时可能无法覆盖，关闭 Excel 后再重试。
- 服务仅绑定 127.0.0.1，无登录功能，只供本机练习，不应直接暴露公网。
- 当前仅输出本地报告，不发送邮件或企业消息。

## 迁移到影刀

未实际创建或运行影刀应用，以下是可迁移设计，不能写成已完成影刀开发。
影刀可负责报表下载、调用 Python 处理模块、读取分类/执行表格与网页表单交互；
业务校验与报表代码可继续复用。需在影刀实际捕获按钮/输入框、设置下载完成检查、
循环与异常分支、运行日志、有限重试，并重新执行同一套样例验收。

商品页面的稳定标签：商品名称、SKU、售价（元）、库存、“保存商品”；
message 区域反馈结果，列表提供可核对的 SKU。优先使用元素定位，避免仅用屏幕坐标。
接入商业后台前，应与业务确认字段、规则、权限及失败后的人工交接流程。
