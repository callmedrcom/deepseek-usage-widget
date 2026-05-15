# Product Roadmap

English | 简体中文

This document defines the current product scope and the planned release direction for DeepSeek Usage Widget.

本文档用于说明 DeepSeek Usage Widget 当前的产品范围，以及后续版本的演进方向。

## Current Scope | 当前范围

Current public baseline: v0.1.0

当前公开基线版本：v0.1.0

Implemented capabilities:

已实现能力：

- Windows desktop always-on-top floating widget
- Balance, daily usage, monthly usage, tokens, request count, and cost display
- Model-level usage breakdown and recent history view
- Data fetching from DeepSeek API, platform token endpoint, CSV/ZIP import, and local ZIP cache fallback
- Local config persistence under the user profile
- API key and platform token encryption at rest on Windows through DPAPI
- Source launch and PyInstaller EXE packaging

- Windows 桌面常驻置顶悬浮窗
- 余额、日用量、月用量、Token、请求次数与费用展示
- 按模型拆分的用量视图和近期历史展示
- 支持 DeepSeek API、平台 token 接口、CSV/ZIP 导入和本地 ZIP 缓存回退
- 用户目录下的本地配置持久化
- API Key 和 Platform Token 在 Windows 上通过 DPAPI 加密存储
- 支持源码运行和 PyInstaller 打包 EXE

Current constraints:

当前限制：

- Windows-focused desktop project
- UI and refresh flow are usable, but operational visibility is still basic
- Automated coverage focuses on parsing, aggregation, crypto, and utility logic; UI and refresh fallback paths need stronger verification

- 当前版本以 Windows 桌面环境为主
- UI 和刷新链路已经可用，但运行状态可见性仍偏基础
- 自动化测试目前主要覆盖解析、聚合、加密和工具函数，UI 与刷新回退链路仍需要补强

## Release Direction | 版本方向

The release strategy is: stabilize first, then improve usability, then expand history and management capabilities.

版本策略为：先做稳定性，再做易用性，最后扩展历史分析和管理能力。

### v0.1.1

Goal: stability and trustworthiness.

目标：稳定性和结果可信度。

Priority: P0

优先级：P0

- Clarify data-source status in the UI, including which source is currently active
- Improve error messages for API, platform token, ZIP download, and cache fallback failures
- Add first-run guidance for API key and platform token configuration
- Add narrow tests around refresh sequencing and settings persistence

- 在界面中明确当前数据来源和命中链路
- 改进 API、平台 token、ZIP 下载和缓存回退的错误提示
- 增加首次启动的 API Key 和 Platform Token 配置引导
- 为刷新顺序和设置持久化补充更窄、更直接的测试

Acceptance criteria:

验收标准：

- Users can tell whether the current data comes from API usage, platform API, downloaded ZIP, or local cache
- When refresh fails, the widget shows a user-readable failure reason instead of a vague generic status
- First-run users can complete the minimum configuration without reading the source code
- Regression tests cover at least the refresh fallback order and settings save/load behavior

- 用户能明确判断当前数据来自 API 用量、平台 API、下载 ZIP 还是本地缓存
- 刷新失败时，组件能展示可理解的失败原因，而不是模糊的通用状态
- 首次使用者无需阅读源码即可完成最小配置
- 回归测试至少覆盖刷新回退顺序和设置保存/加载行为

### v0.2.0

Goal: daily usability.

目标：提升日常使用体验。

Priority: P1

优先级：P1

- System tray support and background minimize behavior
- Startup launch option and better window-position persistence
- Manual date or month switching instead of only showing the latest available view
- Configurable refresh behavior and low-balance reminders
- Better manual control over imported data and active source selection

- 增加系统托盘支持和最小化后台行为
- 支持开机启动和更稳定的窗口位置记忆
- 支持手动切换日期或月份，而不只显示最新可用视图
- 增加可配置刷新策略和低余额提醒
- 提供更明确的导入数据管理和数据源切换能力

Acceptance criteria:

验收标准：

- Closing or minimizing the widget can keep it available from the system tray without terminating the session unexpectedly
- Window position, compact mode, and key display preferences remain consistent across restarts
- Users can inspect a chosen day or month instead of being forced onto the latest available record
- Reminder and refresh options are configurable from the UI and persist correctly

- 关闭或最小化组件后，可通过系统托盘继续访问，而不会意外终止会话
- 窗口位置、紧凑模式和关键显示偏好在重启后保持一致
- 用户可以查看指定日期或月份，而不是被迫只看最新记录
- 提醒和刷新策略可在界面中配置，并能正确持久化

### v0.3.0

Goal: historical value and lightweight analysis.

目标：形成历史价值和轻量分析能力。

Priority: P1

优先级：P1

- Longer-range trend charts for cost, tokens, and requests
- Model comparison over time
- Daily or weekly summary export
- Abnormal spike highlighting and simple cost forecasting
- Improved local archive management for imported and cached records

- 增加费用、Token 和请求量的更长周期趋势图
- 支持模型随时间的对比分析
- 支持导出日报或周报
- 增加异常峰值标记和简单费用预测
- 提升导入数据与缓存数据的本地归档管理能力

Acceptance criteria:

验收标准：

- Users can review at least one longer time range beyond the recent in-widget history
- Exported summaries include enough information to share usage and cost trends outside the app
- Model comparison and spike highlighting help identify abnormal usage without manual spreadsheet work
- Archive management keeps imported records usable without creating duplicate or confusing states

- 用户至少可以查看一个超出当前短周期历史的更长时间范围
- 导出的摘要包含足够信息，可在应用外分享用量和费用趋势
- 模型对比和峰值标记可以帮助用户识别异常用量，而不必手工整理表格
- 归档管理能够保持导入记录可用，且不会制造重复或混乱状态

### v1.0.0

Goal: polished desktop release.

目标：形成成熟的桌面正式版。

Priority: P2

优先级：P2

- Production-ready onboarding and settings experience
- Multi-account or multi-workspace support if real usage proves the need
- Installer or signed distribution workflow
- Optional auto-update path
- Finalize the long-term platform scope after the Windows track is mature

- 提供更完整的首次使用引导和设置体验
- 如果真实使用场景成立，再增加多账号或多工作区支持
- 补齐安装器或签名分发流程
- 视分发方式补充自动更新能力
- 在 Windows 路线成熟后，再决定是否扩展长期平台范围

Acceptance criteria:

验收标准：

- A new user can install or launch the app, complete setup, and understand the main screens without extra documentation
- Release artifacts are packaged in a way suitable for repeatable public distribution
- Optional advanced capabilities such as multi-account support are only included if validated by real user demand
- The Windows desktop experience is stable enough that platform expansion can be evaluated from evidence, not assumption

- 新用户可以安装或启动应用、完成设置，并在不依赖额外文档的情况下理解主要界面
- 发布产物具备可重复、可公开分发的交付形态
- 多账号等高级能力只在真实用户需求被验证后才进入正式范围
- Windows 桌面体验足够稳定后，再基于证据而不是假设评估平台扩展

## Priority Summary | 优先级汇总

- P0: v0.1.1 stability, source visibility, error clarity, and regression coverage
- P1: v0.2.0 usability and v0.3.0 historical analysis
- P2: v1.0.0 release polish and validated expansion scope

- P0：v0.1.1 的稳定性、数据源可见性、错误清晰度和回归覆盖
- P1：v0.2.0 的易用性，以及 v0.3.0 的历史分析能力
- P2：v1.0.0 的正式版交付打磨和经过验证的扩展范围

## Planning Principles | 规划原则

- Do not expand platform scope before the Windows experience is stable
- Prefer reliability and clarity over feature count in the 0.x phase
- Add tests alongside each new slice of data-source or persistence behavior
- Keep the widget lightweight; avoid turning it into a heavy dashboard too early

- 在 Windows 体验稳定之前，不扩展平台范围
- 在 0.x 阶段优先保证可靠性和清晰度，而不是功能数量
- 每新增一段数据源或持久化逻辑时，同步补测试
- 保持组件轻量，不要过早演变成沉重的报表系统