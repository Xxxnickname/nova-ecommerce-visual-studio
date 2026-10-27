$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "首次运行，先安装依赖..." -ForegroundColor Yellow
    $setup = Join-Path $root "scripts\setup.ps1"
    $proc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$setup`"") -Wait -PassThru -WindowStyle Normal
    if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $python)) {
        Write-Host "环境安装未完成，请先运行 scripts\setup.ps1 查看错误。" -ForegroundColor Red
        exit 1
    }
}

$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Start-Process -FilePath $python -ArgumentList "app.py" -WorkingDirectory $root -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Start-Process "http://127.0.0.1:8000"