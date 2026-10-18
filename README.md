# 李佳乐 技术作品集

面向全栈开发与软件研发实习的中文技术作品集，保留自动化、嵌入式和硬件实践，新增设备台账与异常工单个人全栈练习。个人练习说明模拟数据、AI 辅助开发和能力边界。

## 本地预览

在仓库根目录执行 `python -m http.server 8766 --bind 127.0.0.1`，访问 http://127.0.0.1:8766 。
不需要 Node 构建，不依赖外部字体或第三方 CDN。

## 内容

- index.html、styles.css：中文响应式首页、全栈实践、教育与技能、实习与联系方式。
- projects/：设备工单、两个自动化个人练习与三个原有工程项目详情。
- assets/：原项目真实图片、源码架构流程图、实际运行截图。
- automation/：两个新增项目的完整源码、数据、Excel 输出与测试证据，运行方式见该目录 README。
- fullstack/device-desk/：新增 Express + SQLite 服务、前端、锁定依赖及 API 测试。
- downloads/：原自动化源码包及新增设备工单完整源码包。
- verification/：本次验收脚本、测试原始输出、浏览器结果与报告。

原有 ESP32、导盲小车、STM32 饮品系统仓库保持不变，所有链接继续保留。
历史实习成果与新项目模拟指标明确区分；未宣称影刀实际开发经验。
公开 GitHub 主页：https://github.com/lijiale-embed 。

## 部署

保持 GitHub Pages 从 main 根目录发布的现有静态方式。提交推送前须由本人确认。
新增项目源码放在本仓库 automation 中，不创建不存在的新仓库链接。

新增设备平台位于 fullstack/device-desk，GitHub Pages 只展示项目资料，不运行 Node 后端。
GitHub Settings → Pages → Deploy from a branch → main / (root)，保留 .nojekyll，无需构建步骤。
本次没有提交、推送或发布；请检查本地改动后再决定提交。项目详情为真实 HTML 文件，可直接打开和刷新，相对资源路径兼容子目录。

## 设备工单平台本地运行

要求 Node.js 24.x，在另一个终端执行：

```powershell
cd fullstack/device-desk
npm ci
npm start -- --seed
# 打开 http://127.0.0.1:3000
npm test
```

PowerShell 可用 npm.cmd 避免脚本执行策略限制。--seed 仅在空设备表中写入模拟示例；不带该参数启动可验证空数据。默认 SQLite 文件位于 data/device-desk.sqlite，重启保留数据。详细接口、配置、结构和故障排查见 [平台 README](fullstack/device-desk/README.md)。

## 完整验收与源码打包

```powershell
# 仓库根目录，要求已安装 Microsoft Edge
python -m pip install playwright
python verification/check.py
# 生成不含依赖、运行时数据库或日志的源码 ZIP
python verification/package_source.py
```

浏览器脚本使用临时端口和独立数据库，完成后关闭自建服务；生成真实平台截图与 browser-results.json。API 与原 Python 自动化测试输出见 [本次验收报告](verification/REPORT.md)。不新增 Docker 或云平台配置；没有线上后端或容器部署结论。历史硬件项目未重新烧录或进行实物测量。
