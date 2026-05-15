# DeepSeek Usage Widget

[English](README.md) | 简体中文

DeepSeek Usage Widget 是一个基于 Tkinter 的 Windows 桌面悬浮窗，用于实时展示 DeepSeek 账户余额、每日用量、Token 数、请求次数与费用估算。

应用支持从公开 DeepSeek API、DeepSeek Platform 用量接口、导出的 CSV/ZIP 文件以及本地缓存 ZIP 中读取数据，适合 Windows 桌面长期驻留使用，也支持通过 PyInstaller 打包为独立 EXE。

## 功能特性

- 桌面常驻置顶悬浮窗
- 展示每日与月度的 token、请求次数和费用汇总
- 按模型展示用量拆分
- 支持通过浏览器 token 拉取平台侧用量
- 支持 CSV/ZIP 导入与本地缓存回退
- 配置保存在当前用户目录下
- API Key 在 Windows 上通过 DPAPI 加密存储
- 支持一键打包为 EXE

## 预览

项目 Logo：

![DeepSeek Usage Widget logo](logo.png)

DeepSeek 为其各自权利人的商标。本项目是非官方桌面工具，与 DeepSeek 无关联，也未获得其认可或背书。

## 运行环境

- Windows 10 或更高版本
- Python 3.10+
- 用于余额和 API 用量查询的 DeepSeek API Key
- 可选：用于平台侧用量查询的 DeepSeek Platform Token

## 安装

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 源码运行

```powershell
python run_widget.py
```

不要直接运行 `deepseek_usage_widget/widget.py`。应始终通过 `run_widget.py` 启动，以保证包内相对导入在源码运行和 PyInstaller 打包后都能正确工作。

## 打包 EXE

一键打包：

```powershell
build.bat
```

或手动执行：

```powershell
python -m PyInstaller --onefile --windowed --name DeepSeekWidget --add-data "logo.png;." --hidden-import crypto_utils --paths "." run_widget.py
```

## 配置说明

应用会在如下目录保存本地数据：

```text
~/.deepseek_widget/
```

目录内文件包括：

- `config.json`：本地配置，包括加密后的 API Key
- `daily.json`：保存的每日历史用量
- `csv_cache/`：缓存的月度 ZIP 导出文件
- `logo.png`：可选，自定义展示在组件中的 Logo

### API Key

API Key 用于查询余额与 API 用量接口。在 Windows 上，它会通过 DPAPI 加密后再写入本地磁盘。

### Platform Token

Platform Token 为可选项，用于查询 DeepSeek 平台侧用量数据。

获取方式：

1. 打开 `https://platform.deepseek.com/usage`
2. 按 `F12`
3. 打开 Application 或 Storage 面板
4. 找到 Local Storage
5. 复制 `userToken` 的值

## 测试

运行现有单元测试：

```powershell
python test_deepseek_widget.py
```

## 项目结构

```text
.
|-- run_widget.py
|-- crypto_utils.py
|-- build.bat
|-- requirements.txt
|-- deepseek_usage_widget/
|   |-- __init__.py
|   |-- api_client.py
|   |-- config.py
|   |-- models.py
|   |-- utils.py
|   `-- widget.py
`-- test_deepseek_widget.py
```

## 安全与隐私

- 不要提交真实的 API Key 或 Platform Token
- 本地配置存储在用户目录下，不在仓库内
- 对外分享截图、导出文件或缓存文件前，先检查是否泄露用量信息

## 首次发布说明

当前仓库首个公开版本建议使用标签 `v0.1.0`。

- 已补充英文 README 与中文 README
- 已加入 MIT License
- 已清理本地环境、构建产物与诊断脚本的忽略规则
- 已保留 Windows 桌面使用与打包说明

## 发布清单

- 确认 `.gitignore` 已排除本地环境、构建产物与诊断脚本
- 确认仓库内未提交真实密钥或令牌
- 运行现有单元测试
- 正式发布前先本地打包一次 EXE
- 首版发布说明见 [RELEASE_NOTES_v0.1.0.md](RELEASE_NOTES_v0.1.0.md)

## 版本规划

- 当前功能范围与后续版本计划见 [ROADMAP.md](ROADMAP.md)

## 许可证

本项目采用 MIT License，详见 [LICENSE](LICENSE)。
