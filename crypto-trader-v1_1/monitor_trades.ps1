# Crypto Trader Monitor — polls trades and errors every 60s
$API = "http://127.0.0.1:5000"
$LOG = "logs/crash.log"
$CHECK_INTERVAL = 1
$lastTradeCount = 0
$lastLogSize = 0

Write-Host "=== Crypto Trader Monitor ===" -ForegroundColor Cyan
Write-Host "API: $API" -ForegroundColor Gray
Write-Host "Log: $LOG" -ForegroundColor Gray
Write-Host "Checking every ${CHECK_INTERVAL}s" -ForegroundColor Gray
Write-Host ""

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # 1. Check trades
    $trades = $null
    try {
        $trades = Invoke-RestMethod -Uri "$API/api/trades/open" -TimeoutSec 10 -ErrorAction Stop
        $count = if ($trades.Count -ne $null) { $trades.Count } else { @($trades).Count }
        if ($count -gt 0) {
            Write-Host "[$timestamp] TRADES: $count open" -ForegroundColor Green
            foreach ($t in $trades) {
                $pnl = if ($t.pnl) { "$([math]::Round([double]$t.pnl, 2))%" } else { "N/A" }
                Write-Host "  - $$($t.tokenSymbol) | Entry: $($t.price) | PnL: $pnl | Age: $([math]::Round((Get-Date).Subtract([DateTime]$t.timestamp).TotalMinutes, 0))m" -ForegroundColor Yellow
            }
        } else {
            Write-Host "[$timestamp] TRADES: none open" -ForegroundColor DarkGray
        }
        if ($count -ne $lastTradeCount) {
            if ($count -gt $lastTradeCount) {
                Write-Host "[!] NEW TRADE OPENED (was $lastTradeCount, now $count)" -ForegroundColor Magenta
            }
            $lastTradeCount = $count
        }
    } catch {
        Write-Host "[$timestamp] API ERROR: $_" -ForegroundColor Red
    }

    # 2. Check logs for errors (only recent entries)
    if (Test-Path $LOG) {
        $logContent = Get-Content $LOG -Tail 5
        $errors = $logContent | Where-Object { $_ -match "(?<!after 10 retries)Error|CRASH|exception|uncaught" }
        if ($errors) {
            Write-Host "[$timestamp] LOG ERRORS:" -ForegroundColor Red
            foreach ($e in $errors) { Write-Host "  $e" -ForegroundColor Red }
        } else {
            if ($logContent.Length -gt 0) {
                Write-Host "[$timestamp] LOG: last = $($logContent[-1])" -ForegroundColor DarkGray
            }
        }
    }

    # 3. Quick health check
    try {
        $health = Invoke-RestMethod -Uri "$API/api/health" -TimeoutSec 5 -ErrorAction Stop
        if ($health.isRunning -eq $false) {
            Write-Host "[ALERT] Engine is NOT RUNNING!" -ForegroundColor Red -BackgroundColor Black
        }
    } catch {
        Write-Host "[ALERT] Engine UNREACHABLE!" -ForegroundColor Red -BackgroundColor Black
    }

    Start-Sleep -Seconds $CHECK_INTERVAL
}
