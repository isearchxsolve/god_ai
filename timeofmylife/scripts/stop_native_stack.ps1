# Stop the native prototype stack (Meilisearch, MinIO, Qdrant).
# PostgreSQL is a Windows service and is left running.

foreach ($name in @("meilisearch", "minio", "qdrant")) {
    $procs = Get-Process $name -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Output "stopped: $name"
    } else {
        Write-Output "not running: $name"
    }
}
