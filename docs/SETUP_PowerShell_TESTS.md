# Test Setup Guide (Windows / PowerShell)

This guide explains how to prepare your environment to run the test suite and development tools for the Sports Data Pipeline.

## Prerequisites

- Python 3.10+ recommended (3.9 works with our compatibility changes).
- PowerShell (Run as a normal user is fine).

## One‑shot setup (recommended)

Use the helper script to create a virtual environment, install Python deps, install Playwright browsers, and install developer tooling:

```powershell
# From repository root
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1
```

This will:

- Create `.venv/` if missing.
- `pip install -r requirements.txt` (if present), and ensure `pytest` + `playwright` are installed.
- Install Playwright browsers (`python -m playwright install`).
- Install dev tools (`pre-commit`, `ruff`, `black`, `isort`) and `pre-commit install`.

### Script options

```powershell
# Skip creating venv
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1 -CreateVenv:$false

# Skip installing Playwright browsers
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1 -InstallBrowsers:$false

# Skip dev tool installation
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1 -InstallDevTools:$false

# Use a specific Python interpreter
powershell -ExecutionPolicy Bypass -File scripts/setup_tests.ps1 -PythonExe "C:\\Python310\\python.exe"
```

## Running tests

Use the developer helper for common tasks:

```powershell
# Run all tests
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task test

# Run a specific test file (quiet)
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task test -PyTestArgs "tests/test_utils.py -q"
```

## Formatting & linting

```powershell
# Format (isort -> black -> ruff --fix)
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task format

# Lint only
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task lint
```

## Troubleshooting

- If you see `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` during test collection, you might be running Python < 3.10. The codebase is mostly 3.9‑compatible; if you still hit this, ensure your working branch includes the typing compatibility changes or upgrade to Python 3.10+.
- If Playwright complains about missing browsers, run:

  ```powershell
  .\.venv\Scripts\python.exe -m playwright install
  ```

- If pre-commit hooks fail due to formatting, run the formatter and retry your commit:

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task format
  ```

## Locations

- Logs: `Settings.log_file_path` (default: `./logs/`), e.g. `logs/courtside/`, `logs/fbref/`.
- Reports: `./reports/` (e.g. analysis outputs).

---

If you need a Linux/macOS version of this flow, we can add a simple shell script (`scripts/setup_tests.sh`).
