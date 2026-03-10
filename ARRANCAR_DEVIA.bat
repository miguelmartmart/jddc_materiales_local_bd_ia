@echo off
setlocal enabledelayedexpansion
title DEVIA - Arranque del Sistema IA

REM ============================================================
REM  DEVIA - Script Maestro de Arranque (Ultra-Resiliente)
REM  Version: 3.3.0 - 10/03/2026
REM  Servicios:
REM  [1] Backend DEVIA (FastAPI)   Puerto preferido: 8001
REM      Chat IA + BD Firebird + Frontend web
REM      + Constructor de Metadatos BD (/api/metadata-builder)
REM  [2] Backend CodeLab (FastAPI) Puerto preferido: 8002
REM  [3] App Desktop CodeLab (Electron/React)
REM  BD Firebird: 192.168.0.254:3050
REM  IA Local:    http://192.168.0.36 (Qwen3 VL 30B)
REM
REM  RESILIENCIA:
REM  - Docker no corriendo -> pregunta si quiere iniciarlo
REM  - node_modules ausente -> pregunta si quiere npm install
REM  - Puerto ocupado -> intenta liberarlo o usa alternativo
REM  - Electron falla -> continua sin el (solo web)
REM  - Todos los errores quedan en logs/arranque_*.log
REM ============================================================

cd /d "%~dp0"
set "ROOT=%CD%"

REM --- LOG DE ARRANQUE ---
set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul
set "LOG_FILE=%LOG_DIR%\arranque_%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

call :LOG "============================================================"
call :LOG "DEVIA Arranque iniciado v3.3.0"
call :LOG "ROOT=%ROOT%"
call :LOG "============================================================"

REM --- PUERTOS PREFERIDOS Y ALTERNATIVOS ---
set "DEVIA_PORT=8001"
set "DEVIA_PORTS_ALT=8010 8011 8012 8013 8014 8015"
set "CODELAB_PORT=8002"
set "CODELAB_PORTS_ALT=8020 8021 8022"

REM --- ESTADO GLOBAL ---
set "DEVIA_PORT_FINAL="
set "DEVIA_PORT_SAVED="
set "CODELAB_PORT_FINAL="

echo.
echo ============================================================
echo   DEVIA - Sistema de IA para JDDC  [v3.3.0]
echo   Arranque ultra-resiliente del sistema
echo ============================================================
echo.
echo  Que quieres arrancar?
echo.
echo  [1] Solo Chat IA + BD (Backend DEVIA, puerto %DEVIA_PORT%)
echo      Para usar el chat web, las gafas Meta, o la API
echo.
echo  [2] Todo: Chat IA + CodeLab desktop
echo      Backend DEVIA (%DEVIA_PORT%) + CodeLab (%CODELAB_PORT%) + App Electron
echo.
echo  [3] Solo CodeLab desktop
echo      Backend CodeLab (%CODELAB_PORT%) + App Electron
echo.
echo  [4] Diagnostico rapido (sin arrancar nada)
echo      Verifica puertos, BD Firebird, IA local, Docker
echo.
set /p OPCION="  Elige opcion [1-4] (Enter = opcion 1): "
if not defined OPCION set OPCION=1
if "!OPCION!"=="" set OPCION=1
if "!OPCION!"==" " set OPCION=1
if not "!OPCION!"=="1" if not "!OPCION!"=="2" if not "!OPCION!"=="3" if not "!OPCION!"=="4" set OPCION=1
echo [INFO] Opcion seleccionada: !OPCION!
call :LOG "Opcion seleccionada: !OPCION!"

echo.

if "!OPCION!"=="4" goto :DIAGNOSTICO

REM ============================================================
REM  VERIFICACIONES PREVIAS
REM ============================================================
echo [VERIFICANDO] Entorno del sistema...
echo.

call :CHECK_VENV
if "!_VENV_OK!"=="0" (
    echo.
    echo [ERROR CRITICO] No se puede continuar sin el entorno Python.
    call :LOG "ERROR CRITICO: venv no encontrado"
    pause
    exit /b 1
)

call :CHECK_ENV_FILE
call :CHECK_CONFIG_JSON

REM Verificar Docker (no critico — solo informativo + oferta de inicio)
call :CHECK_AND_START_DOCKER

echo.

REM ============================================================
REM  ROUTING SEGUN OPCION
REM ============================================================
if "!OPCION!"=="1" goto :ARRANCAR_DEVIA
if "!OPCION!"=="2" goto :ARRANCAR_DEVIA
if "!OPCION!"=="3" goto :ARRANCAR_CODELAB
goto :FINAL

REM ============================================================
REM  ARRANCAR BACKEND DEVIA
REM ============================================================
:ARRANCAR_DEVIA
echo ============================================================
echo  [1/3] Preparando Backend DEVIA
echo ============================================================
echo.

call :RESOLVE_PORT "%DEVIA_PORT%" "%DEVIA_PORTS_ALT%" DEVIA_PORT_FINAL
if "!DEVIA_PORT_FINAL!"=="" (
    echo.
    echo [ERROR CRITICO] No se encontro ningun puerto libre para el DEVIA.
    echo  Puertos intentados: %DEVIA_PORT% %DEVIA_PORTS_ALT%
    echo  Cierra algunas aplicaciones y vuelve a intentarlo.
    call :LOG "ERROR CRITICO: ningun puerto libre para DEVIA"
    pause
    exit /b 1
)

call :LOG "Puerto DEVIA resuelto: !DEVIA_PORT_FINAL!"
set "DEVIA_PORT_SAVED=!DEVIA_PORT_FINAL!"

echo.
echo  URLs disponibles tras el arranque:
echo    Chat IA web:       http://localhost:!DEVIA_PORT_FINAL!
echo    Constructor BD:    http://localhost:!DEVIA_PORT_FINAL!  (pestana "Constructor BD")
echo    API docs:          http://localhost:!DEVIA_PORT_FINAL!/docs
echo    Health:            http://localhost:!DEVIA_PORT_FINAL!/health
echo    Config chat:       http://localhost:!DEVIA_PORT_FINAL!/api/chat/config
echo    Metadata Builder:  http://localhost:!DEVIA_PORT_FINAL!/api/metadata-builder/status
echo    Desde red:         http://192.168.0.38:!DEVIA_PORT_FINAL!
echo.

set PYTHONPATH=%ROOT%
call :LOG "Lanzando uvicorn en puerto !DEVIA_PORT_FINAL!"
start "DEVIA Backend :!DEVIA_PORT_FINAL!" cmd /k "cd /d %ROOT% && set PYTHONPATH=%ROOT% && echo. && echo === DEVIA Backend - Puerto !DEVIA_PORT_FINAL! === && echo. && .venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port !DEVIA_PORT_FINAL! --log-level info"

echo  Esperando que el backend arranque...
call :WAIT_FOR_DEVIA "!DEVIA_PORT_FINAL!" DEVIA_OK
if "!DEVIA_OK!"=="1" (
    echo [OK] Backend DEVIA arrancado correctamente en puerto !DEVIA_PORT_FINAL!
    call :LOG "DEVIA arrancado OK en puerto !DEVIA_PORT_FINAL!"
) else (
    echo [AVISO] El backend DEVIA no responde aun en el puerto !DEVIA_PORT_FINAL!.
    echo  Puede que tarde un poco mas. Revisa la ventana "DEVIA Backend :!DEVIA_PORT_FINAL!"
    echo  Log de arranque: %LOG_FILE%
    call :LOG "AVISO: DEVIA no responde en puerto !DEVIA_PORT_FINAL! tras espera"
)
echo.

if "!OPCION!"=="1" goto :ABRIR_NAVEGADOR
if "!OPCION!"=="2" goto :ARRANCAR_CODELAB
goto :ABRIR_NAVEGADOR

REM ============================================================
REM  ARRANCAR BACKEND CODELAB
REM ============================================================
:ARRANCAR_CODELAB
echo ============================================================
echo  [2/3] Preparando Backend CodeLab
echo ============================================================
echo.

call :RESOLVE_PORT "%CODELAB_PORT%" "%CODELAB_PORTS_ALT%" CODELAB_PORT_FINAL
if "!CODELAB_PORT_FINAL!"=="" (
    echo [AVISO] No se encontro puerto libre para CodeLab. Continuando sin el.
    call :LOG "AVISO: ningun puerto libre para CodeLab"
    goto :ARRANCAR_ELECTRON
)

call :LOG "Puerto CodeLab resuelto: !CODELAB_PORT_FINAL!"

REM Verificar que existe el servidor CodeLab
if not exist "%ROOT%\desktop-codelab\backend\server.py" (
    echo [AVISO] No se encuentra desktop-codelab\backend\server.py
    echo  Saltando backend CodeLab.
    call :LOG "AVISO: server.py de CodeLab no encontrado"
    goto :ARRANCAR_ELECTRON
)

start "CodeLab Backend :!CODELAB_PORT_FINAL!" cmd /k "cd /d %ROOT% && set PYTHONPATH=%ROOT% && echo. && echo === CodeLab Backend - Puerto !CODELAB_PORT_FINAL! === && echo. && .venv\Scripts\python.exe desktop-codelab\backend\server.py"

echo  Esperando que el backend CodeLab arranque (3 segundos)...
timeout /t 3 /nobreak >nul
echo [OK] Backend CodeLab lanzado en puerto !CODELAB_PORT_FINAL!
echo.

REM ============================================================
REM  ARRANCAR APP ELECTRON
REM ============================================================
:ARRANCAR_ELECTRON
echo ============================================================
echo  [3/3] Preparando App Desktop CodeLab (Electron)
echo ============================================================
echo.

REM Verificar que existe la carpeta desktop-codelab
if not exist "%ROOT%\desktop-codelab" goto :ELECTRON_NO_CARPETA

REM Verificar node_modules
if not exist "%ROOT%\desktop-codelab\node_modules" goto :ELECTRON_SIN_MODULES

REM Verificar que esta compilado
if not exist "%ROOT%\desktop-codelab\dist\electron\main.js" goto :ELECTRON_COMPILAR

goto :ELECTRON_LANZAR

:ELECTRON_NO_CARPETA
echo [AVISO] Carpeta desktop-codelab no encontrada. Saltando Electron.
call :LOG "AVISO: carpeta desktop-codelab no encontrada"
goto :ABRIR_NAVEGADOR

:ELECTRON_SIN_MODULES
echo [AVISO] node_modules no encontrado en desktop-codelab.
echo.
echo  Para usar la app desktop, hay que instalar dependencias npm.
echo  Esto puede tardar 1-3 minutos (solo la primera vez).
echo.
set /p _NPM_RESP="  Quieres instalar ahora? [S/N] (Enter = S): "
if not defined _NPM_RESP set _NPM_RESP=S
if "!_NPM_RESP!"=="" set _NPM_RESP=S
if /i "!_NPM_RESP!"=="N" goto :ELECTRON_SKIP_NPM
if /i "!_NPM_RESP!"=="NO" goto :ELECTRON_SKIP_NPM

echo  Instalando dependencias npm (esto puede tardar)...
call :LOG "Ejecutando npm install en desktop-codelab..."
cd /d "%ROOT%\desktop-codelab"
call npm install >"%LOG_DIR%\npm_install.log" 2>&1
set "_NPM_ERR=!errorlevel!"
cd /d "%ROOT%"
if "!_NPM_ERR!" neq "0" (
    echo [ERROR] npm install fallo. Ver detalles en: %LOG_DIR%\npm_install.log
    call :LOG "ERROR: npm install fallo, ver npm_install.log"
    goto :ABRIR_NAVEGADOR
)
echo [OK] Dependencias npm instaladas correctamente.
call :LOG "npm install OK"
REM Ahora compilar
goto :ELECTRON_COMPILAR

:ELECTRON_SKIP_NPM
echo [INFO] Saltando instalacion npm. La app desktop no estara disponible.
call :LOG "INFO: usuario rechazo npm install, saltando Electron"
goto :ABRIR_NAVEGADOR

:ELECTRON_COMPILAR
echo  Compilando frontend Electron (primera vez o cambios recientes)...
call :LOG "Compilando frontend Electron..."
cd /d "%ROOT%\desktop-codelab"
call npm run build >"%LOG_DIR%\electron_build.log" 2>&1
set "_ELECTRON_BUILD_ERR=!errorlevel!"
cd /d "%ROOT%"
if "!_ELECTRON_BUILD_ERR!" neq "0" (
    echo [ERROR] Fallo la compilacion del frontend Electron.
    echo  Ver detalles en: %LOG_DIR%\electron_build.log
    echo  Continuando sin la app desktop (el chat web sigue disponible).
    call :LOG "ERROR: fallo compilacion Electron, ver electron_build.log"
    goto :ABRIR_NAVEGADOR
)
echo [OK] Compilacion completada.
call :LOG "Compilacion Electron OK"

:ELECTRON_LANZAR
echo  Lanzando app desktop CodeLab...
call :LOG "Lanzando Electron..."
start "CodeLab Desktop App" cmd /k "cd /d %ROOT%\desktop-codelab && echo. && echo === CodeLab Desktop App === && echo. && npm start 2>&1"
echo [OK] App Desktop CodeLab lanzada.
echo.
goto :ABRIR_NAVEGADOR

REM ============================================================
REM  ABRIR NAVEGADOR
REM ============================================================
:ABRIR_NAVEGADOR
REM Recuperar el puerto guardado (DEVIA_PORT_SAVED se setea antes de subrutinas)
if defined DEVIA_PORT_SAVED set "DEVIA_PORT_FINAL=!DEVIA_PORT_SAVED!"
if not defined DEVIA_PORT_FINAL set "DEVIA_PORT_FINAL=8001"
if "!DEVIA_PORT_FINAL!"=="" set "DEVIA_PORT_FINAL=8001"

set "_URL_ABRIR=http://localhost:!DEVIA_PORT_FINAL!"
echo [INFO] Abriendo interfaz web: !_URL_ABRIR!
call :LOG "Abriendo navegador en !_URL_ABRIR!"
timeout /t 2 /nobreak >nul
start "" "!_URL_ABRIR!"
echo [OK] Navegador abierto en !_URL_ABRIR!
echo [INFO] Si no se abrio, copia esta URL en tu navegador: !_URL_ABRIR!
goto :FINAL

REM ============================================================
REM  DIAGNOSTICO COMPLETO
REM ============================================================
:DIAGNOSTICO
echo ============================================================
echo   DIAGNOSTICO COMPLETO DEL SISTEMA DEVIA
echo ============================================================
echo.

echo [1] Entorno Python...
call :CHECK_VENV
echo.

echo [2] Archivos de configuracion...
call :CHECK_ENV_FILE
call :CHECK_CONFIG_JSON
echo.

echo [3] Puertos en uso...
call :SCAN_PORTS
echo.

echo [4] Docker...
call :CHECK_DOCKER_DETAIL
echo.

echo [5] IA local (Qwen3 VL 30B)...
call :CHECK_LOCAL_AI
echo.

echo [6] BD Firebird (192.168.0.254:3050)...
call :CHECK_FIREBIRD
echo.

echo [7] Backend DEVIA (si esta corriendo)...
call :CHECK_DEVIA_RUNNING
echo.

echo [8] Node.js / npm (para Electron)...
call :CHECK_NODE
echo.

echo [9] IP de este PC...
ipconfig | findstr "192.168"
echo.

echo [10] Log de este diagnostico guardado en:
echo    %LOG_FILE%
echo.
goto :FINAL

REM ============================================================
REM  RESUMEN FINAL
REM ============================================================
:FINAL
if "!DEVIA_PORT_FINAL!"=="" set "DEVIA_PORT_FINAL=%DEVIA_PORT%"
echo.
echo ============================================================
echo   SISTEMA DEVIA - RESUMEN
echo ============================================================
echo   Chat IA web:       http://localhost:!DEVIA_PORT_FINAL!
echo   Constructor BD:    http://localhost:!DEVIA_PORT_FINAL!  (pestana "Constructor BD")
echo   Indices SIUO:      http://localhost:!DEVIA_PORT_FINAL!  (pestana "Indices SIUO")
echo   API docs:          http://localhost:!DEVIA_PORT_FINAL!/docs
echo   Health check:      http://localhost:!DEVIA_PORT_FINAL!/health
echo   Desde gafas:       http://192.168.0.38:!DEVIA_PORT_FINAL!
echo   Log de arranque:   %LOG_FILE%
echo ============================================================
echo.
echo   COMANDOS UTILES:
echo.
echo   curl http://localhost:!DEVIA_PORT_FINAL!/health
echo   curl http://localhost:!DEVIA_PORT_FINAL!/api/chat/config
echo   curl http://localhost:!DEVIA_PORT_FINAL!/api/siuo/stats
echo   curl http://localhost:!DEVIA_PORT_FINAL!/api/metadata-builder/status
echo.
echo   Para PARAR todo: ejecuta PARAR_DEVIA.bat
echo ============================================================
echo.
echo  Cierra esta ventana cuando quieras.
echo  Los servidores siguen corriendo en sus propias ventanas.
echo.
call :LOG "Script finalizado. Puerto DEVIA: !DEVIA_PORT_FINAL!"
pause
goto :EOF


REM ============================================================
REM  SUBRUTINAS
REM ============================================================

REM ------------------------------------------------------------
REM  :LOG <mensaje>
REM  Escribe en el log con timestamp
REM ------------------------------------------------------------
:LOG
set "_MSG=%~1"
set "_TS=%date% %time%"
echo [%_TS%] %_MSG% >> "%LOG_FILE%" 2>nul
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_VENV
REM  Verifica que existe el entorno virtual Python
REM  Establece _VENV_OK=1 si OK, _VENV_OK=0 si no existe
REM ------------------------------------------------------------
:CHECK_VENV
set "_VENV_OK=0"
if exist "%ROOT%\.venv\Scripts\uvicorn.exe" set "_VENV_OK=1"
if "!_VENV_OK!"=="1" goto :CHECK_VENV_OK
echo   [ERROR] No se encuentra .venv\Scripts\uvicorn.exe
echo.
echo   Para crear el entorno virtual:
echo     cd %ROOT%
echo     python -m venv .venv
echo     .venv\Scripts\pip install -r requirements.txt
call :LOG "CHECK_VENV: ERROR - uvicorn no encontrado"
goto :EOF
:CHECK_VENV_OK
echo   [OK] Entorno Python (.venv) encontrado
call :LOG "CHECK_VENV: OK"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_ENV_FILE
REM  Verifica o crea el archivo .env
REM ------------------------------------------------------------
:CHECK_ENV_FILE
if exist "%ROOT%\.env" (
    echo   [OK] Archivo .env encontrado
    call :LOG "CHECK_ENV: OK"
    goto :EOF
)
if exist "%ROOT%\.env.example" (
    copy "%ROOT%\.env.example" "%ROOT%\.env" >nul 2>&1
    echo   [AVISO] .env no existia - creado desde .env.example
    echo           Edita %ROOT%\.env con tus claves reales
    call :LOG "CHECK_ENV: creado desde .env.example"
    goto :EOF
)
echo   [ERROR] No existe .env ni .env.example
echo           Crea el archivo .env manualmente
call :LOG "CHECK_ENV: ERROR - ni .env ni .env.example"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_CONFIG_JSON
REM  Verifica o crea el config.json del chat
REM ------------------------------------------------------------
:CHECK_CONFIG_JSON
set "_CFG=%ROOT%\backend\modules\chat\config.json"
if exist "%_CFG%" (
    echo   [OK] config.json del chat encontrado
    call :LOG "CHECK_CONFIG: OK"
    goto :EOF
)
echo   [AVISO] config.json no existe - creando con valores por defecto...
echo {"max_sql_retries": 4, "enable_auto_correction": true, "log_sql_errors": true, "ai_local_only": true} > "%_CFG%"
echo   [OK] config.json creado (modo: solo IA local Qwen3 LAN)
call :LOG "CHECK_CONFIG: creado con valores por defecto"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_AND_START_DOCKER
REM  Verifica Docker. Si esta instalado pero no corriendo,
REM  pregunta al usuario si quiere iniciarlo.
REM  No es critico — el sistema funciona sin Docker.
REM ------------------------------------------------------------
:CHECK_AND_START_DOCKER
set "_DOCKER_AVAILABLE=0"
set "_DOCKER_RUNNING=0"

REM Verificar si Docker esta instalado
where docker >nul 2>&1
if !errorlevel! neq 0 (
    echo   [INFO] Docker no instalado (no es necesario para el chat IA)
    call :LOG "CHECK_DOCKER: no instalado"
    goto :EOF
)
set "_DOCKER_AVAILABLE=1"

REM Verificar si Docker Desktop esta corriendo
docker info >nul 2>&1
if !errorlevel! equ 0 (
    set "_DOCKER_RUNNING=1"
    echo   [OK] Docker Desktop corriendo
    call :LOG "CHECK_DOCKER: corriendo OK"
    goto :EOF
)

REM Docker instalado pero no corriendo
echo   [AVISO] Docker esta instalado pero no esta corriendo.
echo.
echo   Docker no es necesario para el chat IA ni la BD Firebird.
echo   Solo es necesario si usas contenedores Docker en este proyecto.
echo.
set /p _DOCKER_RESP="  Quieres iniciar Docker Desktop ahora? [S/N] (Enter = N): "
if not defined _DOCKER_RESP set _DOCKER_RESP=N
if "!_DOCKER_RESP!"=="" set _DOCKER_RESP=N
if /i "!_DOCKER_RESP!"=="N" goto :DOCKER_SKIP
if /i "!_DOCKER_RESP!"=="NO" goto :DOCKER_SKIP

REM Intentar iniciar Docker Desktop
echo   Iniciando Docker Desktop...
call :LOG "Iniciando Docker Desktop por peticion del usuario..."

REM Buscar Docker Desktop en rutas habituales
set "_DOCKER_EXE="
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    set "_DOCKER_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
)
if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe" (
    set "_DOCKER_EXE=%LOCALAPPDATA%\Docker\Docker Desktop.exe"
)

if "!_DOCKER_EXE!"=="" (
    echo   [AVISO] No se encontro Docker Desktop.exe en rutas habituales.
    echo   Inicialo manualmente desde el menu Inicio.
    call :LOG "AVISO: Docker Desktop.exe no encontrado en rutas habituales"
    goto :EOF
)

start "" "!_DOCKER_EXE!"
echo   Docker Desktop iniciandose. Esperando hasta 60 segundos...
call :LOG "Docker Desktop lanzado: !_DOCKER_EXE!"

REM Esperar hasta 60 segundos a que Docker responda
set "_DOCKER_WAIT=0"
:DOCKER_WAIT_LOOP
set /a "_DOCKER_WAIT+=1"
if !_DOCKER_WAIT! gtr 12 goto :DOCKER_WAIT_TIMEOUT
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] Docker Desktop arrancado correctamente.
    call :LOG "Docker Desktop arrancado OK tras !_DOCKER_WAIT! intentos"
    set "_DOCKER_RUNNING=1"
    goto :EOF
)
echo   Esperando Docker... (intento !_DOCKER_WAIT!/12)
goto :DOCKER_WAIT_LOOP

:DOCKER_WAIT_TIMEOUT
echo   [AVISO] Docker Desktop no respondio en 60 segundos.
echo   Puede que tarde mas. El sistema DEVIA continuara sin Docker.
call :LOG "AVISO: Docker Desktop timeout tras 60s"
goto :EOF

:DOCKER_SKIP
echo   [INFO] Continuando sin Docker.
call :LOG "INFO: usuario rechazo iniciar Docker"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_DOCKER_DETAIL
REM  Version detallada para el diagnostico
REM ------------------------------------------------------------
:CHECK_DOCKER_DETAIL
where docker >nul 2>&1
if !errorlevel! neq 0 (
    echo   [INFO] Docker no esta instalado
    call :LOG "CHECK_DOCKER_DETAIL: no instalado"
    goto :EOF
)
echo   Docker instalado. Verificando estado...
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo   [AVISO] Docker instalado pero no esta corriendo (Docker Desktop apagado)
    call :LOG "CHECK_DOCKER_DETAIL: instalado pero no corriendo"
    goto :EOF
)
echo   [OK] Docker Desktop corriendo. Contenedores activos:
docker ps --format "    ID: {{.ID}}  Nombre: {{.Names}}  Puertos: {{.Ports}}" 2>nul
if !errorlevel! neq 0 (
    echo   (ninguno o error al listar)
)
call :LOG "CHECK_DOCKER_DETAIL: OK"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_NODE
REM  Verifica Node.js y npm para Electron
REM ------------------------------------------------------------
:CHECK_NODE
where node >nul 2>&1
if !errorlevel! neq 0 (
    echo   [INFO] Node.js no instalado (necesario para la app desktop Electron)
    echo   Descarga desde: https://nodejs.org
    call :LOG "CHECK_NODE: no instalado"
    goto :EOF
)
for /f "usebackq delims=" %%v in (`node --version 2^>nul`) do set "_NODE_VER=%%v"
for /f "usebackq delims=" %%v in (`npm --version 2^>nul`) do set "_NPM_VER=%%v"
echo   [OK] Node.js !_NODE_VER! / npm !_NPM_VER!
call :LOG "CHECK_NODE: OK - node !_NODE_VER! npm !_NPM_VER!"
if exist "%ROOT%\desktop-codelab\node_modules" (
    echo   [OK] node_modules encontrado en desktop-codelab
) else (
    echo   [AVISO] node_modules NO encontrado en desktop-codelab
    echo   Ejecuta: cd desktop-codelab ^&^& npm install
)
goto :EOF

REM ------------------------------------------------------------
REM  :GET_PORT_PID <puerto> <var_resultado>
REM  Obtiene el PID del proceso que escucha en el puerto
REM  Resultado en la variable indicada (vacio si libre)
REM ------------------------------------------------------------
:GET_PORT_PID
set "_GP_PORT=%~1"
set "_GP_VAR=%~2"
set "%_GP_VAR%="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "try { $c = Get-NetTCPConnection -LocalPort %_GP_PORT% -State Listen -EA Stop; ($c.OwningProcess | Sort-Object -Unique | Select-Object -First 1).ToString() } catch { '' }" 2^>nul`) do (
    if not "%%p"=="" set "%_GP_VAR%=%%p"
)
goto :EOF

REM ------------------------------------------------------------
REM  :GET_PROCESS_NAME <pid> <var_resultado>
REM  Obtiene el nombre del proceso por PID
REM ------------------------------------------------------------
:GET_PROCESS_NAME
set "_GPN_PID=%~1"
set "_GPN_VAR=%~2"
set "%_GPN_VAR%=desconocido"
for /f "usebackq skip=3 tokens=1" %%n in (`tasklist /FI "PID eq %_GPN_PID%" /FO TABLE /NH 2^>nul`) do (
    if not "%%n"=="" set "%_GPN_VAR%=%%n"
)
goto :EOF

REM ------------------------------------------------------------
REM  :IS_DOCKER_CONTAINER <pid> <var_resultado>
REM  Detecta si el PID pertenece a Docker
REM  var_resultado = "1" si es Docker, "0" si no
REM ------------------------------------------------------------
:IS_DOCKER_CONTAINER
set "_IDC_PID=%~1"
set "_IDC_VAR=%~2"
set "%_IDC_VAR%=0"
call :GET_PROCESS_NAME "%_IDC_PID%" _IDC_NAME
echo !_IDC_NAME! | findstr /i "docker com.docker" >nul 2>&1
if !errorlevel! equ 0 (
    set "%_IDC_VAR%=1"
    goto :EOF
)
for /f "usebackq delims=" %%r in (`powershell -NoProfile -Command "try { $parent = Get-Process -Id (Get-WmiObject Win32_Process -Filter 'ProcessId=%_IDC_PID%').ParentProcessId -EA Stop; if ($parent.Name -match 'docker') { '1' } else { '0' } } catch { '0' }" 2^>nul`) do (
    set "%_IDC_VAR%=%%r"
)
goto :EOF

REM ------------------------------------------------------------
REM  :FIND_DOCKER_CONTAINER_ON_PORT <puerto> <var_id> <var_name>
REM  Busca el contenedor Docker que usa el puerto
REM ------------------------------------------------------------
:FIND_DOCKER_CONTAINER_ON_PORT
set "_FDC_PORT=%~1"
set "_FDC_ID_VAR=%~2"
set "_FDC_NAME_VAR=%~3"
set "%_FDC_ID_VAR%="
set "%_FDC_NAME_VAR%="
docker info >nul 2>&1
if !errorlevel! neq 0 goto :EOF
for /f "usebackq tokens=1,2" %%a in (`docker ps --format "%%ID%% %%Names%%" 2^>nul`) do (
    docker port %%a 2>nul | findstr ":%_FDC_PORT%->" >nul 2>&1
    if !errorlevel! equ 0 (
        set "%_FDC_ID_VAR%=%%a"
        set "%_FDC_NAME_VAR%=%%b"
    )
)
if "!%_FDC_ID_VAR%!"=="" (
    for /f "usebackq tokens=1,2" %%a in (`docker ps --format "%%ID%% %%Names%%" --filter "publish=%_FDC_PORT%" 2^>nul`) do (
        set "%_FDC_ID_VAR%=%%a"
        set "%_FDC_NAME_VAR%=%%b"
    )
)
goto :EOF

REM ------------------------------------------------------------
REM  :TRY_FREE_PORT <puerto> <var_resultado>
REM  Intenta liberar el puerto. var_resultado = "1" si lo logra
REM  Estrategia:
REM    1. Obtener PID
REM    2. Si es Python/uvicorn -> taskkill
REM    3. Si es Docker -> docker stop del contenedor
REM    4. taskkill generico como ultimo recurso
REM ------------------------------------------------------------
:TRY_FREE_PORT
set "_TFP_PORT=%~1"
set "_TFP_RESULT_VAR=%~2"
set "%_TFP_RESULT_VAR%=0"

call :GET_PORT_PID "%_TFP_PORT%" _TFP_PID
if "!_TFP_PID!"=="" (
    set "%_TFP_RESULT_VAR%=1"
    call :LOG "TRY_FREE_PORT %_TFP_PORT%: ya estaba libre"
    goto :EOF
)

call :GET_PROCESS_NAME "!_TFP_PID!" _TFP_PNAME
call :LOG "TRY_FREE_PORT %_TFP_PORT%: ocupado por PID=!_TFP_PID! PROCESO=!_TFP_PNAME!"
echo   Puerto %_TFP_PORT% ocupado por: !_TFP_PNAME! (PID !_TFP_PID!)

REM Estrategia 1: Python/uvicorn
echo !_TFP_PNAME! | findstr /i "python uvicorn" >nul 2>&1
if !errorlevel! equ 0 (
    echo   Detectado proceso Python/uvicorn - intentando taskkill...
    taskkill /F /PID !_TFP_PID! >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [OK] Proceso Python terminado
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: taskkill Python OK"
        timeout /t 1 /nobreak >nul
        set "%_TFP_RESULT_VAR%=1"
        goto :EOF
    )
    echo   [AVISO] taskkill fallo (puede requerir admin)
    call :LOG "TRY_FREE_PORT %_TFP_PORT%: taskkill Python FALLO"
)

REM Estrategia 2: Docker
echo !_TFP_PNAME! | findstr /i "docker com.docker wslrelay" >nul 2>&1
if !errorlevel! equ 0 (
    echo   Detectado proceso Docker - buscando contenedor en puerto %_TFP_PORT%...
    call :FIND_DOCKER_CONTAINER_ON_PORT "%_TFP_PORT%" _TFP_CONT_ID _TFP_CONT_NAME
    if not "!_TFP_CONT_ID!"=="" (
        echo   Contenedor: !_TFP_CONT_NAME! (ID: !_TFP_CONT_ID!)
        echo   Ejecutando: docker stop !_TFP_CONT_ID!
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: docker stop !_TFP_CONT_ID! (!_TFP_CONT_NAME!)"
        docker stop !_TFP_CONT_ID! >nul 2>&1
        if !errorlevel! equ 0 (
            echo   [OK] Contenedor Docker detenido: !_TFP_CONT_NAME!
            echo   [INFO] Para reiniciarlo: docker start !_TFP_CONT_ID!
            call :LOG "TRY_FREE_PORT %_TFP_PORT%: docker stop OK"
            timeout /t 2 /nobreak >nul
            set "%_TFP_RESULT_VAR%=1"
            goto :EOF
        )
        echo   [ERROR] No se pudo detener el contenedor Docker
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: docker stop FALLO"
    ) else (
        echo   [AVISO] No se identifico el contenedor Docker para el puerto %_TFP_PORT%
        docker ps 2>nul | findstr "%_TFP_PORT%"
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: contenedor Docker no identificado"
    )
)

REM Estrategia 3: taskkill generico
echo   Intentando taskkill generico (PID !_TFP_PID!)...
taskkill /F /PID !_TFP_PID! >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] Proceso terminado (taskkill generico)
    call :LOG "TRY_FREE_PORT %_TFP_PORT%: taskkill generico OK"
    timeout /t 1 /nobreak >nul
    set "%_TFP_RESULT_VAR%=1"
    goto :EOF
)

echo   [AVISO] No se pudo liberar el puerto %_TFP_PORT% automaticamente
call :LOG "TRY_FREE_PORT %_TFP_PORT%: todos los intentos fallaron"
goto :EOF

REM ------------------------------------------------------------
REM  :IS_PORT_FREE <puerto> <var_resultado>
REM  Comprueba si el puerto esta libre. var = "1" si libre
REM ------------------------------------------------------------
:IS_PORT_FREE
set "_IPF_PORT=%~1"
set "_IPF_VAR=%~2"
set "%_IPF_VAR%=0"
call :GET_PORT_PID "%_IPF_PORT%" _IPF_PID
if "!_IPF_PID!"=="" set "%_IPF_VAR%=1"
goto :EOF

REM ------------------------------------------------------------
REM  :RESOLVE_PORT <puerto_preferido> <puertos_alt> <var_resultado>
REM  Resuelve el puerto a usar:
REM    1. Intenta el puerto preferido (liberar si ocupado)
REM    2. Si no puede, prueba los alternativos
REM    3. Devuelve el puerto resuelto o vacio si no hay ninguno
REM ------------------------------------------------------------
:RESOLVE_PORT
set "_RP_PREF=%~1"
set "_RP_ALTS=%~2"
set "_RP_VAR=%~3"
set "%_RP_VAR%="

echo   Comprobando puerto preferido %_RP_PREF%...
call :IS_PORT_FREE "%_RP_PREF%" _RP_FREE
if "!_RP_FREE!"=="1" (
    echo   [OK] Puerto %_RP_PREF% libre
    set "%_RP_VAR%=%_RP_PREF%"
    call :LOG "RESOLVE_PORT: puerto preferido %_RP_PREF% libre"
    goto :EOF
)

echo   Puerto %_RP_PREF% ocupado. Intentando liberar...
call :TRY_FREE_PORT "%_RP_PREF%" _RP_FREED
if "!_RP_FREED!"=="1" (
    timeout /t 1 /nobreak >nul
    call :IS_PORT_FREE "%_RP_PREF%" _RP_FREE2
    if "!_RP_FREE2!"=="1" (
        echo   [OK] Puerto %_RP_PREF% liberado y disponible
        set "%_RP_VAR%=%_RP_PREF%"
        call :LOG "RESOLVE_PORT: puerto %_RP_PREF% liberado OK"
        goto :EOF
    )
)

echo   No se pudo liberar el puerto %_RP_PREF%. Buscando alternativo...
call :LOG "RESOLVE_PORT: buscando alternativo a %_RP_PREF%"

for %%A in (%_RP_ALTS%) do (
    if "!%_RP_VAR%!"=="" (
        call :IS_PORT_FREE "%%A" _RP_ALT_FREE
        if "!_RP_ALT_FREE!"=="1" (
            echo   [OK] Puerto alternativo disponible: %%A
            set "%_RP_VAR%=%%A"
            call :LOG "RESOLVE_PORT: usando alternativo %%A"
        ) else (
            echo   Puerto %%A ocupado, probando siguiente...
        )
    )
)

if "!%_RP_VAR%!"=="" (
    echo   [ERROR] Ningun puerto disponible en la lista: %_RP_PREF% %_RP_ALTS%
    call :LOG "RESOLVE_PORT: ERROR - ningun puerto disponible"
)
goto :EOF

REM ------------------------------------------------------------
REM  :WAIT_FOR_DEVIA <puerto> <var_resultado>
REM  Espera hasta 15 segundos a que el DEVIA responda
REM  Verifica que es el DEVIA (no otro servicio)
REM  var_resultado = "1" si OK
REM ------------------------------------------------------------
:WAIT_FOR_DEVIA
set "_WFD_PORT=%~1"
set "_WFD_VAR=%~2"
set "%_WFD_VAR%=0"
set "_WFD_TRIES=0"

:WAIT_LOOP
set /a "_WFD_TRIES+=1"
if !_WFD_TRIES! gtr 5 goto :WAIT_TIMEOUT

echo   Intento !_WFD_TRIES!/5 - esperando respuesta en puerto %_WFD_PORT%...
timeout /t 3 /nobreak >nul

curl -s --max-time 3 http://localhost:%_WFD_PORT%/health >nul 2>&1
if !errorlevel! neq 0 goto :WAIT_LOOP

for /f "usebackq delims=" %%r in (`curl -s --max-time 3 http://localhost:%_WFD_PORT%/health 2^>nul`) do (
    set "_WFD_RESP=%%r"
)
call :LOG "WAIT_FOR_DEVIA: respuesta health = !_WFD_RESP!"

echo !_WFD_RESP! | findstr /i "DEVIA" >nul 2>&1
if !errorlevel! equ 0 (
    set "%_WFD_VAR%=1"
    goto :EOF
)

echo   [AVISO] El puerto %_WFD_PORT% responde pero no es el DEVIA: !_WFD_RESP!
call :LOG "WAIT_FOR_DEVIA: puerto responde pero no es DEVIA: !_WFD_RESP!"
goto :WAIT_LOOP

:WAIT_TIMEOUT
echo   [AVISO] Timeout esperando al DEVIA (15 segundos)
call :LOG "WAIT_FOR_DEVIA: timeout"
goto :EOF

REM ------------------------------------------------------------
REM  :SCAN_PORTS
REM  Muestra el estado de los puertos relevantes
REM ------------------------------------------------------------
:SCAN_PORTS
for %%P in (8001 8002 8010 8011 8012 8020) do (
    call :GET_PORT_PID "%%P" _SP_PID
    if "!_SP_PID!"=="" (
        echo   Puerto %%P: LIBRE
    ) else (
        call :GET_PROCESS_NAME "!_SP_PID!" _SP_NAME
        echo   Puerto %%P: OCUPADO por !_SP_NAME! (PID !_SP_PID!)
    )
)
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_LOCAL_AI
REM  Verifica que la IA local Qwen3 responde
REM ------------------------------------------------------------
:CHECK_LOCAL_AI
curl -s --max-time 5 http://192.168.0.36/api/vlm/v1/models -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY=" >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] IA local Qwen3 VL 30B accesible (192.168.0.36)
    call :LOG "CHECK_LOCAL_AI: OK via IP directa"
    goto :EOF
)
curl -s --max-time 5 http://jddcia.local/api/vlm/v1/models -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY=" >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] IA local accesible via jddcia.local
    call :LOG "CHECK_LOCAL_AI: OK via jddcia.local"
    goto :EOF
)
echo   [AVISO] IA local no accesible (192.168.0.36 ni jddcia.local)
echo   El sistema usara fallback a Groq/Gemini si ai_local_only=false
call :LOG "CHECK_LOCAL_AI: no accesible"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_FIREBIRD
REM  Verifica conectividad con Firebird (via Python)
REM ------------------------------------------------------------
:CHECK_FIREBIRD
if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo   [AVISO] No hay .venv para verificar Firebird
    goto :EOF
)
"%ROOT%\.venv\Scripts\python.exe" -c "import socket; s=socket.create_connection(('192.168.0.254',3050),timeout=3); s.close(); print('  [OK] BD Firebird accesible (192.168.0.254:3050)')" 2>nul
if !errorlevel! neq 0 (
    echo   [AVISO] BD Firebird no accesible en 192.168.0.254:3050
    echo   Verifica que el servidor Firebird esta encendido y en red
    call :LOG "CHECK_FIREBIRD: no accesible"
    goto :EOF
)
call :LOG "CHECK_FIREBIRD: OK"
goto :EOF

REM ------------------------------------------------------------
REM  :CHECK_DEVIA_RUNNING
REM  Verifica si el DEVIA esta corriendo y en que puerto
REM ------------------------------------------------------------
:CHECK_DEVIA_RUNNING
set "_CDR_FOUND=0"
for %%P in (8001 8010 8011 8012 8013 8014 8015) do (
    if "!_CDR_FOUND!"=="0" (
        for /f "usebackq delims=" %%r in (`curl -s --max-time 2 http://localhost:%%P/health 2^>nul`) do (
            echo %%r | findstr /i "DEVIA" >nul 2>&1
            if !errorlevel! equ 0 (
                echo   [OK] DEVIA corriendo en puerto %%P
                echo   Respuesta: %%r
                set "_CDR_FOUND=1"
                call :LOG "CHECK_DEVIA_RUNNING: corriendo en puerto %%P"
            )
        )
    )
)
if "!_CDR_FOUND!"=="0" (
    echo   [INFO] DEVIA no detectado en ninguno de los puertos habituales
    echo   Puertos comprobados: 8001 8010 8011 8012 8013 8014 8015
    call :LOG "CHECK_DEVIA_RUNNING: no detectado"
)
goto :EOF
