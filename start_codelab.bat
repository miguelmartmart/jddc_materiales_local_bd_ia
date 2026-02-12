@echo off
setlocal
title AI Code Lab Launcher

echo ===================================================
echo      AI Code Lab - Sistema de Inicio
echo ===================================================
echo.

:: 1. Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado. Por favor instalalo y agregalo al PATH.
    pause
    exit /b 1
)
echo [OK] Python detectado.

:: 2. Verificar Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js no encontrado. Por favor instalalo.
    pause
    exit /b 1
)
echo [OK] Node.js detectado.

echo.
echo Iniciando servicios...
echo.

:: 3. Iniciar Backend (Servidor Python)
echo [1/2] Lanzando Backend (Puerto 8002)...
cd desktop-codelab
start "AI CodeLab - Backend" cmd /k "python backend/server.py"

:: Esperar unos segundos para que el backend arranque
timeout /t 3 >nul

:: 4. Iniciar Frontend (Electron/React)
echo [2/2] Lanzando Cliente de Escritorio...
echo       (Compilando cambios recientes...)
cd desktop-codelab
call npm run build
echo       (Iniciando aplicacion...)
:: Usamos npm start que ejecuta "electron ."
call npm start

echo.
echo ===================================================
echo      Sesion Finalizada
echo ===================================================
pause
