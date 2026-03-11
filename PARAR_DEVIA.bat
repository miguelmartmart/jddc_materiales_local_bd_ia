@echo off
chcp 65001 >nul 2>&1
title DEVIA — Parar todos los servidores

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║          DEVIA — Parando todos los servidores           ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM Matar por puerto 8001 (Backend DEVIA)
echo [1] Parando Backend DEVIA (puerto 8001)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    echo     Matando PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)
netstat -ano | findstr ":8001 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (echo     [OK] Puerto 8001 liberado) else (echo     [AVISO] Puerto 8001 aun activo)

REM Matar por puerto 8002 (Backend CodeLab)
echo [2] Parando Backend CodeLab (puerto 8002)...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8002 " ^| findstr "LISTENING"') do (
    echo     Matando PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)
netstat -ano | findstr ":8002 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% neq 0 (echo     [OK] Puerto 8002 liberado) else (echo     [AVISO] Puerto 8002 aun activo)

REM Matar Electron
echo [3] Parando App Desktop (Electron)...
taskkill /F /IM electron.exe /T >nul 2>&1
if %errorlevel% equ 0 (echo     [OK] Electron parado) else (echo     [INFO] Electron no estaba corriendo)

echo.
echo [OK] Sistema DEVIA parado completamente.
echo.
pause
