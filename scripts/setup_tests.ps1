param(
    [switch]$CreateVenv = $true,
    [switch]$InstallBrowsers = $true,
    [switch]$InstallDevTools = $true,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

function Get-Python {
    param([string]$Explicit)
    if ($Explicit -ne "") { return $Explicit }
    # Prefer project venv python if it exists
    $venvPy = Join-Path -Path (Resolve-Path ".").Path -ChildPath ".venv/Scripts/python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    return "python"
}

function New-ProjectVenv {
    $venvDir = ".venv"
    if (-not (Test-Path $venvDir)) {
        Write-Host "Creating virtual environment at $venvDir ..." -ForegroundColor Cyan
        python -m venv $venvDir
    } else {
        Write-Host "Virtual environment already exists at $venvDir" -ForegroundColor Yellow
    }
}

function Install-PythonDeps {
    param([string]$Py)
    Write-Host "Installing project dependencies with $Py ..." -ForegroundColor Cyan
    & $Py -m pip install --upgrade pip
    if (Test-Path "requirements.txt") {
        & $Py -m pip install -r requirements.txt
    } else {
        Write-Host "requirements.txt not found; installing minimal test deps" -ForegroundColor Yellow
    }
    # Ensure pytest and playwright are available for tests
    & $Py -m pip install pytest pytest-asyncio playwright
}

function Install-PlaywrightBrowsers {
    param([string]$Py)
    Write-Host "Installing Playwright browsers ..." -ForegroundColor Cyan
    & $Py -m playwright install
}

function Install-DevTools {
    param([string]$Py)
    Write-Host "Installing developer tools (pre-commit, ruff, black, isort) ..." -ForegroundColor Cyan
    & $Py -m pip install pre-commit ruff black isort
    Write-Host "Installing pre-commit hooks ..." -ForegroundColor Cyan
    pre-commit install
}

try {
    if ($CreateVenv) { New-ProjectVenv }
    $PY = Get-Python -Explicit $PythonExe

    Install-PythonDeps -Py $PY

    if ($InstallBrowsers) { Install-PlaywrightBrowsers -Py $PY }
    if ($InstallDevTools) { Install-DevTools -Py $PY }

    Write-Host "\nSetup complete." -ForegroundColor Green
    Write-Host "Run tests with:" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task test -PyTestArgs \"tests/test_utils.py -q\"" -ForegroundColor Gray
    Write-Host "Or all tests:" -ForegroundColor Green
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 -Task test" -ForegroundColor Gray
}
catch {
    Write-Error $_
    exit 1
}
