# Generate the secret files referenced by docker-compose.yml under ./secrets/.
# Skips files that already exist. All files are gitignored.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

New-Item -ItemType Directory -Path secrets -Force | Out-Null

function New-SecretFile {
    param([string]$Name, [int]$Bytes = 32, [string]$Encoding = "base64")
    $path = Join-Path "secrets" $Name
    if (Test-Path $path) {
        Write-Output "exists: $path"
        return
    }
    $raw = [byte[]]::new($Bytes)
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($raw)
    $rng.Dispose()
    $value = if ($Encoding -eq "hex") {
        -join ($raw | ForEach-Object { $_.ToString("x2") })
    } else {
        [Convert]::ToBase64String($raw)
    }
    Set-Content -Path $path -Value $value -NoNewline -Encoding ascii
    Write-Output "created: $path"
}

New-SecretFile "postgres_password.txt"
New-SecretFile "redis_password.txt"
New-SecretFile "n8n_encryption_key.txt" -Encoding hex
New-SecretFile "minio_secret_key.txt" -Bytes 24

$minioAccess = Join-Path "secrets" "minio_access_key.txt"
if (-not (Test-Path $minioAccess)) {
    Set-Content -Path $minioAccess -Value "minio-admin" -NoNewline -Encoding ascii
    Write-Output "created: $minioAccess"
} else {
    Write-Output "exists: $minioAccess"
}

Write-Output "`nDone. Keep ./secrets/ out of version control (already gitignored)."
