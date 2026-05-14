# Release v0.1.0

Initial public release of DeepSeek Usage Widget.

DeepSeek Usage Widget 首个公开版本。

## Download And Run | 下载与运行

- Download `DeepSeekWidget-v0.1.0-windows-x64.zip`
- Extract the entire archive to any folder
- Double-click `DeepSeekWidget.exe` to run
- No installation required, unzip and use

- 下载 `DeepSeekWidget-v0.1.0-windows-x64.zip`
- 将整个压缩包解压到任意目录
- 双击 `DeepSeekWidget.exe` 即可运行
- 无需安装，解压即用

## Highlights | 主要特性

- Windows desktop overlay built with Tkinter
- Real-time balance, usage, token, request, and cost display
- DeepSeek platform usage import through token or CSV/ZIP export
- Local encrypted API key storage with Windows DPAPI
- PyInstaller build script for standalone EXE packaging

- 基于 Tkinter 的 Windows 桌面悬浮窗
- 实时显示余额、用量、Token、请求次数与费用
- 支持通过 token 或 CSV/ZIP 导入平台侧用量
- API Key 在本地通过 Windows DPAPI 加密存储
- 提供 PyInstaller 打包脚本，可生成独立 EXE

## Included In This Release | 本次发布包含

- English and Simplified Chinese project documentation
- MIT license
- Prebuilt Windows executable package
- Existing widget, API client, config, utility, and test modules

- 英文与简体中文项目文档
- MIT 许可证
- 预编译 Windows 可执行文件压缩包
- 现有组件、API 客户端、配置、工具与测试模块

## Verification | 验证情况

- Launcher import smoke test passed
- `python test_deepseek_widget.py` passed locally

- 启动入口导入检查已通过
- `python test_deepseek_widget.py` 已在本地通过

## Known Constraints | 已知限制

- Windows-focused project

- 当前版本主要面向 Windows 桌面环境
