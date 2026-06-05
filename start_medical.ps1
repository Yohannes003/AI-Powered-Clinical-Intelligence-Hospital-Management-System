$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Write-Host "Starting medical stack with docker-compose..."
$exitCode = & docker-compose up -d --build

if ($LASTEXITCODE -eq 0) {
    Write-Host "Docker Compose completed successfully. Opening frontend..."
    Start-Process "http://localhost:8080"
} else {
    Write-Error "Docker Compose failed with exit code $LASTEXITCODE"
}
