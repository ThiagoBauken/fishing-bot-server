@echo off
echo ==========================================
echo   Rebuilding Fishing Bot Server Docker
echo ==========================================
echo.

echo 1. Stopping old container...
docker stop fishing-bot-server 2>nul
docker rm fishing-bot-server 2>nul

echo.
echo 2. Building new image...
docker build -t fishing-bot-server:latest .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Build successful!
    echo.
    echo 3. Starting new container...

    docker run -d ^
      --name fishing-bot-server ^
      -p 8122:8122 ^
      -e PORT=8122 ^
      -e KEYMASTER_URL=https://private-keygen.pbzgje.easypanel.host ^
      -e PROJECT_ID=67a4a76a-d71b-4d07-9ba8-f7e794ce0578 ^
      fishing-bot-server:latest

    echo.
    echo [SUCCESS] Container started!
    echo.
    echo 4. Checking logs...
    timeout /t 3 >nul
    docker logs fishing-bot-server --tail 20

    echo.
    echo ==========================================
    echo [SUCCESS] Rebuild complete!
    echo ==========================================
    echo.
    echo Test health: curl http://localhost:8122/health
) else (
    echo.
    echo [ERROR] Build failed! Check errors above.
    pause
    exit /b 1
)

pause
