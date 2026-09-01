@echo off
setlocal EnableDelayedExpansion
title DEVIA — Instalacion automatica
color 0A

echo.
echo  ============================================================
echo       DEVIA — Instalacion en nuevo PC
echo       Sistema de Gestion IA + Acceso BD SQL Obras
echo  ============================================================
echo.

:: ── 1. Verificar Python ────────────────────────────────────────
echo [1/7] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python no encontrado.
    echo.
    echo  Instala Python 3.10 o superior desde:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANTE: Marca "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK] %%v detectado

:: ── 2. Verificar Git ────────────────────────────────────────────
echo.
echo [2/7] Verificando Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [AVISO] Git no encontrado. Si ya tienes el codigo, puedes saltarte esto.
    echo  Si necesitas clonar el repositorio, instala Git desde:
    echo    https://git-scm.com/download/win
) else (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo  [OK] %%v detectado
)

:: ── 3. Crear entorno virtual ────────────────────────────────────
echo.
echo [3/7] Creando entorno virtual Python (.venv)...
if exist .venv (
    echo  [OK] Entorno virtual ya existe, saltando creacion.
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo  [OK] Entorno virtual creado en .venv\
)

:: ── 4. Instalar dependencias ────────────────────────────────────
echo.
echo [4/7] Instalando dependencias Python (puede tardar 2-5 minutos)...
echo       Se instalaran ~77 paquetes: FastAPI, uvicorn, Firebird, IA, etc.
echo.
call .venv\Scripts\pip.exe install --upgrade pip --quiet
call .venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo  [ERROR] Fallo la instalacion de dependencias.
    echo  Revisa requirements.txt y la conexion a internet.
    pause
    exit /b 1
)
echo  [OK] Dependencias instaladas correctamente.

:: ── 5. Verificar .env ────────────────────────────────────────────
echo.
echo [5/7] Verificando configuracion (.env)...
if exist .env (
    echo  [OK] Archivo .env encontrado.
    echo  Recuerda verificar que DB_HOST, DB_NAME y DB_PASSWORD son correctos
    echo  para este PC y su acceso al servidor Firebird/SQL Obras.
) else (
    echo  [AVISO] No existe .env. Creando desde la plantilla...
    copy .env.example .env >nul
    echo.
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║  ACCION REQUERIDA: Edita el archivo .env                ║
    echo  ║                                                          ║
    echo  ║  Abre .env con Notepad y configura:                     ║
    echo  ║    DB_HOST     = IP del servidor Firebird (ej: 192.168.0.10)  ║
    echo  ║    DB_NAME     = Ruta completa a la BD en el servidor   ║
    echo  ║    DB_PASSWORD = Password de Firebird                   ║
    echo  ║                                                          ║
    echo  ║  Luego vuelve a ejecutar iniciar.bat                    ║
    echo  ╚══════════════════════════════════════════════════════════╝
    echo.
    start notepad .env
    pause
    exit /b 0
)

:: ── 6. Verificar driver Firebird ──────────────────────────────────
echo.
echo [6/7] Verificando conexion a base de datos...
call .venv\Scripts\python.exe -c "import fdb; print('  [OK] Driver Firebird (fdb) disponible')" 2>nul
if %errorlevel% neq 0 (
    call .venv\Scripts\python.exe -c "import firebirdsql; print('  [OK] Driver Firebird (firebirdsql) disponible')" 2>nul
    if %errorlevel% neq 0 (
        echo  [AVISO] Driver Firebird no detectado correctamente.
        echo  El sistema intentara conectar igualmente al iniciar.
    )
)

echo.
echo [7/7] Instalacion completada.
echo.
echo  ============================================================
echo   Para iniciar DEVIA ejecuta:
echo.
echo     iniciar.bat
echo.
echo   O manualmente:
echo     .venv\Scripts\python.exe start_backend.py
echo.
echo   Luego abre en el navegador:
echo     http://localhost:8001
echo  ============================================================
echo.
pause
