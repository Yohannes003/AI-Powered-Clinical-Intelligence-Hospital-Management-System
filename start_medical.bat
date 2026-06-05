@echo off
cd /d "%~dp0"

echo Starting medical stack with docker-compose...

docker-compose up -d --build
if errorlevel 1 (
    echo Docker Compose failed.
    exit /b %errorlevel%
)

echo Docker Compose completed successfully. Opening frontend...
start "" "http://localhost:8080"
