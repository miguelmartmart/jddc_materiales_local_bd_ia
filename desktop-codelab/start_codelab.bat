@echo off
cd /d "%~dp0"
echo ==========================================
echo    INICIANDO AI CODE LAB - DESKTOP
echo ==========================================

:: Verificar Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js no esta instalado o no esta en el PATH.
    pause
    exit /b 1
)

:: Verificar Python (para el backend)
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ADVERTENCIA] Python no detectado. El backend de IA podria no funcionar.
)

echo.
echo Iniciando aplicacion...
echo.

:: Ejecutar npm start
call npm start

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La aplicacion se cerro con errores.
    pause
)
