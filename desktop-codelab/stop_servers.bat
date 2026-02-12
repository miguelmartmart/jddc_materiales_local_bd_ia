@echo off
echo Stopping AI Code Lab servers...

:: Kill Python Backend
taskkill /F /IM python.exe /T >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend server stopped.
) else (
    echo [INFO] Backend server was not running.
)

:: Kill Node/Electron processes
taskkill /F /IM node.exe /T >nul 2>&1
taskkill /F /IM electron.exe /T >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Desktop app stopped.
) else (
    echo [INFO] Desktop app was not running.
)

echo.
echo All servers stopped.
pause
