# Bring up the full Docker Compose stack (requires Docker Desktop running,
# i.e. WSL2 with hardware virtualization enabled).
# Preconditions checked: .env exists, ./secrets/ populated.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path .env)) {
    Write-Error ".env not found - copy .env.example to .env and fill it in."
}

$requiredSecrets = @(
    "postgres_password.txt",
    "redis_password.txt",
    "n8n_encryption_key.txt",
    "minio_access_key.txt",
    "minio_secret_key.txt"
)
foreach ($secret in $requiredSecrets) {
    if (-not (Test-Path (Join-Path "secrets" $secret))) {
        Write-Error "secrets/$secret missing - run scripts\generate_secrets.ps1 first."
    }
}

docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker daemon not reachable. Enable virtualization in BIOS, start Docker Desktop (WSL2 backend), then re-run."
}

docker compose up -d
docker compose ps
