param(
    [ValidateSet("format","lint","test","setup","all")]
    [string]$Task = "all",
    [string]$PyTestArgs = ""
)

$ErrorActionPreference = "Stop"

function Ensure-VenvTools {
    Write-Host "Ensuring developer tools are installed (pre-commit, ruff, black, isort, pytest)" -ForegroundColor Cyan
    python -m pip install --upgrade pre-commit ruff black isort pytest | Out-Null
}

function Run-Setup {
    Ensure-VenvTools
    Write-Host "Installing pre-commit hooks..." -ForegroundColor Cyan
    pre-commit install
    Write-Host "Running pre-commit on all files (first time may take a bit)..." -ForegroundColor Cyan
    pre-commit run --all-files
}

function Run-Format {
    Ensure-VenvTools
    Write-Host "Running isort ..." -ForegroundColor Green
    isort . --profile=black --line-length=100
    Write-Host "Running black ..." -ForegroundColor Green
    black . --line-length=100
    Write-Host "Running ruff --fix (with unsafe fixes for unused imports) ..." -ForegroundColor Green
    ruff check . --fix --unsafe-fixes
}

function Run-Lint {
    Ensure-VenvTools
    Write-Host "Running ruff (lint only)..." -ForegroundColor Yellow
    ruff check .
}

function Run-Test {
    Ensure-VenvTools
    if ([string]::IsNullOrWhiteSpace($PyTestArgs)) {
        Write-Host "Running pytest (all tests)..." -ForegroundColor Magenta
        pytest -q
    } else {
        Write-Host "Running pytest with args: $PyTestArgs" -ForegroundColor Magenta
        pytest $PyTestArgs
    }
}

switch ($Task) {
    "setup"  { Run-Setup }
    "format" { Run-Format }
    "lint"   { Run-Lint }
    "test"   { Run-Test }
    "all"    {
        Run-Format
        Run-Lint
        Run-Test
    }
}
