# DeepSeek Usage Widget

DeepSeek Usage Widget is a Windows desktop overlay built with Tkinter. It shows DeepSeek account balance, daily usage, token counts, request counts, and estimated cost in a compact always-on-top window.

The app can read usage from the public DeepSeek API, the DeepSeek Platform usage endpoint, exported CSV/ZIP files, and locally cached ZIP files. It is designed for Windows desktop use and can be packaged into a standalone EXE with PyInstaller.

## Features

- Always-on-top desktop widget for DeepSeek usage and balance
- Daily and monthly token, request, and cost summaries
- Model-level usage breakdown
- Platform usage import through browser token
- CSV/ZIP export parsing with local cache fallback
- Local configuration persisted under the user profile
- API key encryption at rest on Windows through DPAPI
- One-click EXE packaging with PyInstaller

## Preview

Project logo:

![DeepSeek Usage Widget logo](logo.png)

DeepSeek is a trademark of its respective owner. This project is an unofficial desktop utility and is not affiliated with or endorsed by DeepSeek.

## Requirements

- Windows 10 or later
- Python 3.10+
- A DeepSeek API key for balance and API usage requests
- Optional: a DeepSeek platform token to read platform usage data

## Installation

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run From Source

```powershell
python run_widget.py
```

Do not run `deepseek_usage_widget/widget.py` directly. Use `run_widget.py` so package-relative imports work correctly in both source and PyInstaller builds.

## Build EXE

One-click build:

```powershell
build.bat
```

Or run PyInstaller manually:

```powershell
python -m PyInstaller --onefile --windowed --name DeepSeekWidget --hidden-import crypto_utils --paths "." run_widget.py
```

## Configuration

The app stores local data in the following directory:

```text
~/.deepseek_widget/
```

Files created there:

- `config.json`: local settings, including the encrypted API key
- `daily.json`: saved daily usage history
- `csv_cache/`: cached monthly ZIP exports
- `logo.png`: optional custom logo shown in the widget

### API Key

The API key is used for balance and API usage endpoints. On Windows it is encrypted locally with DPAPI before being written to disk.

### Platform Token

The platform token is optional and is used to query DeepSeek platform usage data.

How to get it:

1. Open `https://platform.deepseek.com/usage` in a browser.
2. Press `F12`.
3. Open Application or Storage tools.
4. Find Local Storage.
5. Copy the `userToken` value.

## Tests

Run the unit tests:

```powershell
python test_deepseek_widget.py
```

## Project Structure

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

## Security And Privacy Notes

- Do not commit your real API key or platform token.
- Local config is stored outside the repository under your user profile.
- Review screenshots and cached exports before sharing them publicly because they may reveal usage information.

## Release Checklist

- Confirm `.gitignore` excludes local environments, caches, and build outputs.
- Verify no secrets are present in tracked files.
- Run the unit tests.
- Build the EXE once before publishing a release.
- Add a GitHub repository description and topics after the first push.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).