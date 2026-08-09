# Start the native (Docker-free) prototype stack from tools/bin:
#   Meilisearch :7700   MinIO :9000/:9001   Qdrant :6333
# PostgreSQL runs as the native Windows service postgresql-x64-18.
# Secrets are read from .env at the repo root.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path .env)) {
    Write-Error ".env not found - copy .env.example to .env and fill it in."
}

function Get-EnvVar {
    param([string]$Name)
    $line = Select-String -Path .env -Pattern "^$Name=(.*)$"
    if ($null -eq $line) { throw "Missing $Name in .env" }
    return $line.Matches[0].Groups[1].Value
}

New-Item -ItemType Directory -Path tools\data -Force | Out-Null

function Start-IfNotRunning {
    param([string]$ProcessName, [string]$ExePath, [string[]]$ExeArgs, [hashtable]$EnvVars = @{})
    if (Get-Process $ProcessName -ErrorAction SilentlyContinue) {
        Write-Output "$ProcessName already running"
        return
    }
    foreach ($key in $EnvVars.Keys) {
        Set-Item -Path "env:$key" -Value $EnvVars[$key]
    }
    $sp = @{ FilePath = $ExePath; WindowStyle = "Hidden" }
    if ($ExeArgs -and $ExeArgs.Count -gt 0) { $sp.ArgumentList = $ExeArgs }
    Start-Process @sp | Out-Null
    Write-Output "$ProcessName started"
}

Start-IfNotRunning "meilisearch" "tools\bin\meilisearch.exe" @(
    "--db-path", "tools\data\meilisearch",
    "--http-addr", "localhost:7700",
    "--no-analytics"
) @{ MEILI_MASTER_KEY = Get-EnvVar "MEILI_MASTER_KEY" }

Start-IfNotRunning "minio" "tools\bin\minio.exe" @(
    "server", "tools\data\minio",
    "--address", ":9000", "--console-address", ":9001"
) @{
    MINIO_ROOT_USER = Get-EnvVar "MINIO_ROOT_USER"
    MINIO_ROOT_PASSWORD = Get-EnvVar "MINIO_ROOT_PASSWORD"
}

Start-IfNotRunning "qdrant" "tools\bin\qdrant\qdrant.exe" @() @{
    QDRANT__STORAGE__STORAGE_PATH = Join-Path (Get-Location) "tools\data\qdrant"
}

Start-Sleep -Seconds 5

$checks = @{
    "Meilisearch" = "http://localhost:7700/health"
    "MinIO"       = "http://localhost:9000/minio/health/live"
    "Qdrant"      = "http://localhost:6333/collections"
}
foreach ($name in $checks.Keys) {
    try {
        Invoke-WebRequest -Uri $checks[$name] -TimeoutSec 5 -UseBasicParsing | Out-Null
        Write-Output "[OK]   $name"
    } catch {
        Write-Output "[FAIL] $name - $($_.Exception.Message)"
    }
}
