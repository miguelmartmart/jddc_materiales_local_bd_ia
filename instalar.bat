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
echo [1/7] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python no encontrado en el PATH.
    echo.
    echo  SOLUCION:
    echo  1. Descarga Python 3.10 desde: https://www.python.org/downloads/
    echo  2. Durante instalacion: marca "Add Python to PATH"
    echo  3. Si ya instalaste SIN marcar PATH, ve a:
    echo     Panel de control - Sistema - Variables de entorno
    echo     Añade a PATH de USUARIO:
    echo       C:\Users\TUUSUARIO\AppData\Local\Programs\Python\Python310\
    echo       C:\Users\TUUSUARIO\AppData\Local\Programs\Python\Python310\Scripts\
    echo  4. Cierra y vuelve a abrir esta ventana
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
    echo  [AVISO] Git no encontrado. Si ya tienes el codigo, puedes continuar sin el.
    echo  Para futuras actualizaciones instala Git: https://git-scm.com/download/win
) else (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo  [OK] %%v detectado
)

:: ── 3. Crear entorno virtual ────────────────────────────────────
echo.
echo [3/7] Creando entorno virtual Python (.venv)...
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
    echo  [OK] Entorno virtual creado en .venv\
)

:: ── 4. Actualizar pip ───────────────────────────────────────────
echo.
echo [4/7] Actualizando pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet 2>nul
echo  [OK] pip listo

:: ── 5. Instalar dependencias ────────────────────────────────────
echo.
echo [5/7] Instalando dependencias (3-5 minutos la primera vez)...
echo       FastAPI, uvicorn, Firebird, Gemini, OpenAI, Groq...
echo.

:: Generar lista de produccion (sin comentarios ni paquetes de test)
.venv\Scripts\python.exe -c "lines=open('requirements.txt',encoding='utf-8').readlines();prod=[l for l in lines if l.strip() and not l.strip().startswith('#') and 'pytest' not in l and 'annotated-doc' not in l];open('_req_prod.txt','w',encoding='utf-8').writelines(prod);print('  Paquetes a instalar: '+str(len(prod)))"

call .venv\Scripts\pip.exe install -r _req_prod.txt --no-warn-script-location
set _INSTALL_ERR=%errorlevel%
del _req_prod.txt 2>nul

if %_INSTALL_ERR% neq 0 (
    echo.
    echo  [ERROR] Fallo al instalar dependencias.
    echo.
    echo  Causas comunes:
    echo    - Sin conexion a internet
    echo    - Antivirus bloqueando pip (desactivalo temporalmente)
    echo    - Ejecuta como Administrador
    echo.
    echo  Instalacion minima manual (abre PowerShell en la carpeta):
    echo    .venv\Scripts\pip install fastapi uvicorn python-dotenv requests
    echo    .venv\Scripts\pip install fdb firebirdsql
    echo    .venv\Scripts\pip install google-generativeai openai groq
    echo.
    pause
    exit /b 1
)
echo  [OK] Dependencias instaladas correctamente.

:: Instalar herramientas de test (opcionales, no criticas para el servidor)
echo.
echo  Instalando herramientas de test (opcionales)...
call .venv\Scripts\pip.exe install "pytest>=9.0" "pytest-asyncio>=0.21" --quiet --no-warn-script-location 2>nul
if %errorlevel% neq 0 (
    echo  [INFO] Tests opcionales omitidos (no afectan al funcionamiento del servidor).
) else (
    echo  [OK] Herramientas de test instaladas.
)

:: ── 6. Crear o verificar .env ──────────────────────────────────
echo.
echo [6/7] Verificando configuracion (.env)...
if exist .env (
    echo  [OK] .env encontrado.
    echo.
    echo  Revisa que estos valores sean correctos para ESTE PC:
    echo    DB_HOST     = IP del servidor Firebird en la red
    echo    DB_NAME     = Ruta al archivo .fdb tal como la ve el servidor
    echo    DB_PASSWORD = Password de Firebird
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
        echo  [OK] .env basico creado
    )
    echo.
    echo  =========================================================
    echo   ACCION REQUERIDA: Edita el archivo .env
    echo.
    echo   Configura DB_HOST, DB_NAME y DB_PASSWORD para este PC.
    echo   Luego ejecuta: ARRANCAR_DEVIA.bat
    echo  =========================================================
    echo.
    start notepad .env
    pause
    exit /b 0
)

:: ── 7. Verificar driver Firebird ───────────────────────────────
echo.
echo [7/7] Verificando drivers de base de datos...
.venv\Scripts\python.exe -c "import fdb; print('  [OK] Driver fdb disponible')" 2>nul
if %errorlevel% neq 0 (
    .venv\Scripts\python.exe -c "import firebirdsql; print('  [OK] Driver firebirdsql disponible')" 2>nul
    if %errorlevel% neq 0 (
        echo  [INFO] Driver se verificara al iniciar el servidor.
    )
)

echo.
echo  ============================================================
echo   INSTALACION COMPLETADA
echo.
echo   Siguiente paso:
echo     1. Doble clic en ARRANCAR_DEVIA.bat
echo     2. Elige opcion 1 (Solo Chat IA + BD)
echo     3. Abre en el navegador: http://localhost:8001
echo  ============================================================
echo.
pause
