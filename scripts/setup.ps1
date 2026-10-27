$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $root ".venv"

function Find-Python {
    $candidates = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $resolved = & py -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates += $resolved.Trim() }
        } catch {}
    }
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        try {
            $version = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]"3.10") { return $candidate }
        } catch {}
    }
    return $null
}

Write-Host "NOVA - 环境安装" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $venv)) {
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        Write-Host "未找到 Python 3.10 或更高版本，请先安装并勾选 Add Python to PATH。" -ForegroundColor Red
        Read-Host "按 Enter 关闭"
        exit 1
    }
    Write-Host "使用 Python：$pythonExe"
    & $pythonExe -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "虚拟环境创建失败" }
}

$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "找不到虚拟环境 Python：$python" }
& $python -m pip install --disable-pip-version-check --upgrade pip
& $python -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
& $python -c "import fastapi, uvicorn, requests, PIL, pytest, httpx, multipart; print('依赖检查通过')"
Write-Host "安装完成。双击 scripts\start.vbs 即可启动。" -ForegroundColor Green