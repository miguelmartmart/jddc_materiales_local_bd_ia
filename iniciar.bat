@echo off
setlocal EnableDelayedExpansion
title DEVIA — Iniciando sistema
color 0A

echo.
echo  ============================================================
echo       DEVIA — Iniciando servidor
echo  ============================================================
echo.

:: Verificar que existe .env
if not exist .env (
    echo  [ERROR] No existe el archivo .env
    echo  Ejecuta primero: instalar.bat
    pause
    exit /b 1
)

:: Verificar que existe .venv
if not exist .venv\Scripts\python.exe (
    echo  [ERROR] Entorno virtual no encontrado.
    echo  Ejecuta primero: instalar.bat
    pause
    exit /b 1
)

echo  Iniciando backend DEVIA en puerto 8001...
echo  Accede desde el navegador a: http://localhost:8001
echo.
echo  Para detener el servidor: cierra esta ventana o pulsa Ctrl+C
echo  ============================================================
echo.

.venv\Scripts\python.exe start_backend.py

pause
