@echo off
setlocal EnableDelayedExpansion
title DEVIA — Instalacion automatica
color 0A
chcp 65001 >nul 2>&1

echo.
echo  ============================================================
echo       DEVIA — Instalacion en nuevo PC
echo  ============================================================
echo.

:: ── 1. Verificar Python ────────────────────────────────────────
echo [1/8] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python no encontrado en el PATH.
    echo.
    echo  SOLUCION:
    echo  1. Descarga Python 3.10 desde: https://www.python.org/downloads/
    echo  2. Durante instalacion: marca "Add Python to PATH"
    echo  3. Si ya instalaste SIN marcar PATH:
    echo     Panel de control - Sistema - Variables de entorno
    echo     Añade a PATH de USUARIO:
    echo       C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\
    echo       C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\Scripts\
    echo  4. Cierra y vuelve a abrir esta ventana
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [OK] %%v detectado

:: ── 2. Verificar Git ────────────────────────────────────────────
echo.
echo [2/8] Verificando Git...
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Git no instalado. Puedes continuar si ya tienes el codigo.
) else (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo  [OK] %%v detectado
)

:: ── 3. Crear entorno virtual ────────────────────────────────────
echo.
echo [3/8] Creando entorno virtual Python (.venv)...
if exist .venv\Scripts\python.exe (
    echo  [OK] Entorno virtual ya existe.
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERROR] No se pudo crear el entorno virtual.
        echo  Prueba abrir como Administrador y volver a ejecutar.
        pause
        exit /b 1
    )
    echo  [OK] Entorno virtual creado.
)

:: ── 4. Actualizar pip ───────────────────────────────────────────
echo.
echo [4/8] Actualizando pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet 2>nul
echo  [OK] pip listo

:: ── 5. Servidor web (critico) ───────────────────────────────────
echo.
echo [5/8] Instalando servidor web (FastAPI + uvicorn)...
call .venv\Scripts\pip.exe install "fastapi>=0.110.0,<0.125.0" "uvicorn>=0.27.0" "python-multipart>=0.0.9" "python-dotenv>=1.0.0" "pydantic>=2.6.0" "pydantic-settings>=2.2.0" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo  [ERROR] Fallo instalando FastAPI/uvicorn.
    echo  Comprueba la conexion a internet y vuelve a intentarlo.
    pause
    exit /b 1
)
echo  [OK] Servidor web listo

:: ── 6. HTTP + Bases de datos ────────────────────────────────────
echo.
echo [6/8] Instalando HTTP y drivers Firebird...
call .venv\Scripts\pip.exe install "requests>=2.31.0" "httpx>=0.27.0" "aiohttp>=3.9.0" "aiofiles>=23.0.0" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    call .venv\Scripts\pip.exe install requests httpx aiohttp aiofiles --quiet --no-warn-script-location
)

call .venv\Scripts\pip.exe install "fdb>=2.0" --quiet --no-warn-script-location 2>nul
call .venv\Scripts\pip.exe install "firebirdsql>=1.2.0" --quiet --no-warn-script-location 2>nul
echo  [OK] HTTP y BD listos

:: ── 7. IA por grupos independientes ────────────────────────────
echo.
echo [7/8] Instalando modulos de IA (2-4 minutos)...

echo  Instalando Google Gemini...
call .venv\Scripts\pip.exe install "google-generativeai>=0.7.0" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo  [AVISO] Gemini con conflicto, intentando sin restriccion de version...
    call .venv\Scripts\pip.exe install google-generativeai --quiet --no-warn-script-location
    if %errorlevel% neq 0 (
        echo  [AVISO] Gemini no disponible. Se usara Groq/OpenAI como IA.
    )
)

echo  Instalando OpenAI y Groq...
call .venv\Scripts\pip.exe install "openai>=1.50.0" "groq>=0.11.0" --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    call .venv\Scripts\pip.exe install openai groq --quiet --no-warn-script-location
)

echo  Instalando utilidades...
call .venv\Scripts\pip.exe install "PyYAML>=6.0" "passlib>=1.7.4" "pillow>=10.0.0" "tqdm>=4.65.0" "Pygments>=2.15.0" "colorama>=0.4.6" "python-dateutil>=2.8.0" --quiet --no-warn-script-location 2>nul

echo  Instalando herramientas de test (opcionales)...
call .venv\Scripts\pip.exe install "pytest>=9.0" "pytest-asyncio>=0.21" --quiet --no-warn-script-location 2>nul

echo  [OK] Modulos de IA listos

:: ── 8. Verificar y crear .env ──────────────────────────────────
echo.
echo [8/8] Verificando configuracion (.env)...
if exist .env (
    echo  [OK] .env encontrado.
    echo.
    echo  Revisa que son correctos para ESTE PC:
    echo    DB_HOST     = IP del servidor Firebird
    echo    DB_NAME     = Ruta al .fdb en el servidor
    echo    DB_PASSWORD = Password Firebird (por defecto: masterkey)
) else (
    echo  Creando .env desde plantilla...
    if exist .env.example (
        copy .env.example .env >nul
        echo  [OK] .env creado desde .env.example
    ) else (
        echo DB_HOST=192.168.0.254> .env
        echo DB_PORT=3050>> .env
        echo DB_NAME=C:\SQL Obras\DATOS\EMPRESA.FDB>> .env
        echo DB_USER=SYSDBA>> .env
        echo DB_PASSWORD=masterkey>> .env
        echo AI_LOCAL_ONLY=false>> .env
        echo DEVIA_PORT=8001>> .env
    )
    echo.
    echo  ACCION REQUERIDA: Edita .env con tus datos de conexion.
    echo  Luego ejecuta: ARRANCAR_DEVIA.bat
    echo.
    start notepad .env
    pause
    exit /b 0
)

echo.
echo  ============================================================
echo   INSTALACION COMPLETADA
echo.
echo   Siguiente paso:
echo     1. Doble clic en: ARRANCAR_DEVIA.bat
echo     2. Elige opcion 1 (Solo Chat IA + BD)
echo     3. Abre en el navegador: http://localhost:8001
echo  ============================================================
echo.
pause
