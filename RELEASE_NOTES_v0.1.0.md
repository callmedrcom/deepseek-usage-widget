# Release v0.1.0

Initial public release of DeepSeek Usage Widget.

## Highlights

- Windows desktop overlay built with Tkinter
- Real-time balance, usage, token, request, and cost display
- DeepSeek platform usage import through token or CSV/ZIP export
- Local encrypted API key storage with Windows DPAPI
- PyInstaller build script for standalone EXE packaging

## Included In This Release

- English and Simplified Chinese project documentation
- MIT license
- Cleaned repository ignore rules for local and build-only files
- Existing widget, API client, config, utility, and test modules

## Verification

- Launcher import smoke test passed
- `python test_deepseek_widget.py` passed locally

## Known Constraints

- Windows-focused project
