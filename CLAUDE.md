# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DeepSeek Usage Widget — a Windows desktop Tkinter overlay that displays DeepSeek API usage, balance, and cost in real time. PyInstaller builds it into a standalone `DeepSeekWidget.exe`.

## Commands

```bash
# Run from source
python run_widget.py

# Build EXE (one-click)
build.bat

# Or manually
python -m PyInstaller --onefile --windowed --name DeepSeekWidget \
  --hidden-import crypto_utils --paths "." run_widget.py

# Verify package integrity
python -c "from run_widget import main"
```

## Architecture

```
run_widget.py              # Entry point (absolute imports — required by PyInstaller)
crypto_utils.py            # Windows DPAPI encrypt/decrypt for API key at rest
deepseek_usage_widget/
  __init__.py              # Re-exports main, DeepSeekWidget
  widget.py                # Tkinter UI: DeepSeekWidget(Tk), SettingsWindow(Toplevel)
  api_client.py            # DeepSeekAPI (balance, usage JSON, CSV/ZIP export endpoints)
                           #   + _parse_csv_zip, _parse_deepseek_csv, _aggregate_usage
  config.py                # load/save config (JSON), load/save/merge daily history
  models.py                # Constants: paths (~/.deepseek_widget/), THEME dict,
                           #   DEFAULT_CONFIG with model pricing, MODEL_META labels
  utils.py                 # Date formatting, _load_local_zip (offline ZIP import),
                           #   _api_error_msg
```

**Key constraint**: `widget.py` uses relative imports (`from .models import ...`). It must be run as part of the package — never directly. The launcher `run_widget.py` handles this for both source runs and PyInstaller entry points.

**Config storage**: `~/.deepseek_widget/config.json` (API key DPAPI-encrypted) and `~/.deepseek_widget/daily.json` (usage history keyed by ISO8601 date).

**API client**: Talks to `api.deepseek.com` (balance, usage) and `platform.deepseek.com` (CSV export download). Falls back to local ZIP files when offline.
