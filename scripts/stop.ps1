$connections = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $connections) { Write-Host "服务未运行"; exit 0 }
$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $processIds) { Stop-Process -Id $processId -Force }
Write-Host "NOVA 服务已停止" -ForegroundColor Green