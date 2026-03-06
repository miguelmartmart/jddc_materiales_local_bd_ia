@echo off
setlocal enabledelayedexpansion
title DEVIA - Arranque del Sistema IA

REM ============================================================
REM  DEVIA - Script Maestro de Arranque (Ultra-Resiliente)
REM  Version: 3.1.0 - 06/03/2026
REM  Servicios:
REM  [1] Backend DEVIA (FastAPI)   Puerto preferido: 8001
REM      Chat IA + BD Firebird + Frontend web
REM      + Constructor de Metadatos BD (/api/metadata-builder)
REM  [2] Backend CodeLab (FastAPI) Puerto preferido: 8002
REM  [3] App Desktop CodeLab (Electron/React)
REM  BD Firebird: 192.168.0.254:3050
REM  IA Local:    http://192.168.0.36 (Qwen3 VL 30B)
REM ============================================================

cd /d "%~dp0"
set "ROOT=%CD%"

REM --- LOG DE ARRANQUE ---
set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul
set "LOG_FILE=%LOG_DIR%\arranque_%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

call :LOG "============================================================"
call :LOG "DEVIA Arranque iniciado"
call :LOG "ROOT=%ROOT%"
call :LOG "============================================================"

REM --- PUERTOS PREFERIDOS Y ALTERNATIVOS ---
set "DEVIA_PORT=8001"
set "DEVIA_PORTS_ALT=8010 8011 8012 8013 8014 8015"
set "CODELAB_PORT=8002"
set "CODELAB_PORTS_ALT=8020 8021 8022"

echo.
echo ============================================================
echo   DEVIA - Sistema de IA para JDDC  [v3.1.0]
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
if "%OPCION%"=="" set OPCION=1
call :LOG "Opcion elegida: %OPCION%"

echo.

if "%OPCION%"=="4" goto :DIAGNOSTICO

REM ============================================================
REM  VERIFICACIONES PREVIAS
REM ============================================================
echo [VERIFICANDO] Entorno del sistema...
echo.

call :CHECK_VENV
if errorlevel 1 (
    echo.
    echo [ERROR CRITICO] No se puede continuar sin el entorno Python.
    call :LOG "ERROR CRITICO: venv no encontrado"
    pause
    exit /b 1
)

call :CHECK_ENV_FILE
call :CHECK_CONFIG_JSON

echo.

REM ============================================================
REM  ROUTING SEGUN OPCION
REM ============================================================
if "%OPCION%"=="1" goto :ARRANCAR_DEVIA
if "%OPCION%"=="2" goto :ARRANCAR_DEVIA
if "%OPCION%"=="3" goto :ARRANCAR_CODELAB
goto :FINAL

REM ============================================================
REM  ARRANCAR BACKEND DEVIA
REM ============================================================
:ARRANCAR_DEVIA
echo ============================================================
echo  [1/3] Preparando Backend DEVIA...
echo ============================================================
echo.

REM Resolver el puerto para DEVIA
call :RESOLVE_PORT "%DEVIA_PORT%" "%DEVIA_PORTS_ALT%" DEVIA_PORT_FINAL
if "%DEVIA_PORT_FINAL%"=="" (
    echo.
    echo [ERROR CRITICO] No se encontro ningun puerto libre para el DEVIA.
    echo  Puertos intentados: %DEVIA_PORT% %DEVIA_PORTS_ALT%
    echo  Cierra algunas aplicaciones y vuelve a intentarlo.
    call :LOG "ERROR CRITICO: ningun puerto libre para DEVIA"
    pause
    exit /b 1
)

call :LOG "Puerto DEVIA resuelto: %DEVIA_PORT_FINAL%"

echo.
echo  URLs disponibles tras el arranque:
echo    Chat IA web:       http://localhost:%DEVIA_PORT_FINAL%
echo    Constructor BD:    http://localhost:%DEVIA_PORT_FINAL%  (pestana "Constructor BD")
echo    API docs:          http://localhost:%DEVIA_PORT_FINAL%/docs
echo    Health:            http://localhost:%DEVIA_PORT_FINAL%/health
echo    Config chat:       http://localhost:%DEVIA_PORT_FINAL%/api/chat/config
echo    Metadata Builder:  http://localhost:%DEVIA_PORT_FINAL%/api/metadata-builder/status
echo    Desde red:         http://192.168.0.38:%DEVIA_PORT_FINAL%
echo.

set PYTHONPATH=%ROOT%
call :LOG "Lanzando uvicorn en puerto %DEVIA_PORT_FINAL%"
start "DEVIA Backend :%DEVIA_PORT_FINAL%" cmd /k "cd /d %ROOT% && set PYTHONPATH=%ROOT% && echo. && echo === DEVIA Backend - Puerto %DEVIA_PORT_FINAL% === && echo. && .venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port %DEVIA_PORT_FINAL% --log-level info"

echo  Esperando que el backend arranque...
call :WAIT_FOR_DEVIA "%DEVIA_PORT_FINAL%" DEVIA_OK
if "%DEVIA_OK%"=="1" (
    echo [OK] Backend DEVIA arrancado correctamente en puerto %DEVIA_PORT_FINAL%
    call :LOG "DEVIA arrancado OK en puerto %DEVIA_PORT_FINAL%"
) else (
    echo [ERROR] El backend DEVIA no responde en el puerto %DEVIA_PORT_FINAL%.
    echo  Revisa la ventana "DEVIA Backend :%DEVIA_PORT_FINAL%" para ver el error.
    echo  Log de arranque: %LOG_FILE%
    call :LOG "ERROR: DEVIA no responde en puerto %DEVIA_PORT_FINAL%"
)
echo.

if "%OPCION%"=="1" goto :ABRIR_NAVEGADOR
if "%OPCION%"=="2" goto :ARRANCAR_CODELAB
goto :ABRIR_NAVEGADOR

REM ============================================================
REM  ARRANCAR BACKEND CODELAB
REM ============================================================
:ARRANCAR_CODELAB
echo ============================================================
echo  [2/3] Preparando Backend CodeLab...
echo ============================================================
echo.

call :RESOLVE_PORT "%CODELAB_PORT%" "%CODELAB_PORTS_ALT%" CODELAB_PORT_FINAL
if "%CODELAB_PORT_FINAL%"=="" (
    echo [AVISO] No se encontro puerto libre para CodeLab. Continuando sin el.
    call :LOG "AVISO: ningun puerto libre para CodeLab"
    goto :ARRANCAR_ELECTRON
)

call :LOG "Puerto CodeLab resuelto: %CODELAB_PORT_FINAL%"

if not exist "%ROOT%\desktop-codelab\node_modules" (
    echo [AVISO] node_modules no encontrado en desktop-codelab
    echo  Ejecuta primero: cd desktop-codelab ^&^& npm install
    call :LOG "AVISO: node_modules no encontrado en desktop-codelab"
)

start "CodeLab Backend :%CODELAB_PORT_FINAL%" cmd /k "cd /d %ROOT% && set PYTHONPATH=%ROOT% && echo. && echo === CodeLab Backend - Puerto %CODELAB_PORT_FINAL% === && echo. && .venv\Scripts\python.exe desktop-codelab\backend\server.py"

echo  Esperando que el backend CodeLab arranque (3 segundos)...
timeout /t 3 /nobreak >nul
echo [OK] Backend CodeLab lanzado en puerto %CODELAB_PORT_FINAL%
echo.

REM ============================================================
REM  ARRANCAR APP ELECTRON
REM ============================================================
:ARRANCAR_ELECTRON
echo ============================================================
echo  [3/3] Preparando App Desktop CodeLab (Electron)...
echo ============================================================
echo.

if not exist "%ROOT%\desktop-codelab\node_modules" (
    echo [ERROR] node_modules no encontrado. Saltando Electron.
    echo  Ejecuta: cd desktop-codelab ^&^& npm install
    call :LOG "ERROR: node_modules no encontrado, saltando Electron"
    goto :ABRIR_NAVEGADOR
)

if not exist "%ROOT%\desktop-codelab\dist\electron\main.js" (
    echo  Compilando frontend (primera vez o cambios recientes)...
    call :LOG "Compilando frontend Electron..."
    cd /d "%ROOT%\desktop-codelab"
    call npm run build >"%LOG_DIR%\electron_build.log" 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la compilacion del frontend Electron.
        echo  Ver detalles en: %LOG_DIR%\electron_build.log
        call :LOG "ERROR: fallo compilacion Electron, ver electron_build.log"
        cd /d "%ROOT%"
        goto :ABRIR_NAVEGADOR
    ) else (
        echo [OK] Compilacion completada
        call :LOG "Compilacion Electron OK"
    )
    cd /d "%ROOT%"
)

call :LOG "Lanzando Electron..."
start "CodeLab Desktop App" cmd /k "cd /d %ROOT%\desktop-codelab && echo. && echo === CodeLab Desktop App === && echo. && npm start 2>&1"
echo [OK] App Desktop CodeLab lanzada
echo.
goto :ABRIR_NAVEGADOR

REM ============================================================
REM  ABRIR NAVEGADOR
REM ============================================================
:ABRIR_NAVEGADOR
if "%DEVIA_PORT_FINAL%"=="" set DEVIA_PORT_FINAL=%DEVIA_PORT%
echo [INFO] Abriendo interfaz web en el navegador...
call :LOG "Abriendo navegador en http://localhost:%DEVIA_PORT_FINAL%"
timeout /t 2 /nobreak >nul
start "" "http://localhost:%DEVIA_PORT_FINAL%"
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

echo [4] Contenedores Docker activos...
call :CHECK_DOCKER
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

echo [8] IP de este PC...
ipconfig | findstr "192.168"
echo.

echo [9] Log de este diagnostico guardado en:
echo    %LOG_FILE%
echo.
goto :FINAL

REM ============================================================
REM  RESUMEN FINAL
REM ============================================================
:FINAL
if "%DEVIA_PORT_FINAL%"=="" set DEVIA_PORT_FINAL=%DEVIA_PORT%
echo.
echo ============================================================
echo   SISTEMA DEVIA - RESUMEN
echo ============================================================
echo   Chat IA web:       http://localhost:%DEVIA_PORT_FINAL%
echo   Constructor BD:    http://localhost:%DEVIA_PORT_FINAL%  (pestana "Constructor BD")
echo   Indices SIUO:      http://localhost:%DEVIA_PORT_FINAL%  (pestana "Indices SIUO")
echo   API docs:          http://localhost:%DEVIA_PORT_FINAL%/docs
echo   Health check:      http://localhost:%DEVIA_PORT_FINAL%/health
echo   Desde gafas:       http://192.168.0.38:%DEVIA_PORT_FINAL%
echo   Log de arranque:   %LOG_FILE%
echo ============================================================
echo.
echo   COMANDOS UTILES:
echo.
echo   curl http://localhost:%DEVIA_PORT_FINAL%/health
echo   curl http://localhost:%DEVIA_PORT_FINAL%/api/chat/config
echo   curl http://localhost:%DEVIA_PORT_FINAL%/api/siuo/stats
echo   curl http://localhost:%DEVIA_PORT_FINAL%/api/metadata-builder/status
echo.
echo   Para PARAR todo: ejecuta PARAR_DEVIA.bat
echo ============================================================
echo.
echo  Cierra esta ventana cuando quieras.
echo  Los servidores siguen corriendo en sus propias ventanas.
echo.
call :LOG "Script finalizado. Puerto DEVIA: %DEVIA_PORT_FINAL%"
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
REM  Devuelve errorlevel 1 si no existe
REM ------------------------------------------------------------
:CHECK_VENV
if exist "%ROOT%\.venv\Scripts\uvicorn.exe" (
    echo   [OK] Entorno Python (.venv) encontrado
    call :LOG "CHECK_VENV: OK"
    exit /b 0
) else (
    echo   [ERROR] No se encuentra .venv\Scripts\uvicorn.exe
    echo.
    echo   Para crear el entorno virtual:
    echo     cd %ROOT%
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    call :LOG "CHECK_VENV: ERROR - uvicorn no encontrado"
    exit /b 1
)

REM ------------------------------------------------------------
REM  :CHECK_ENV_FILE
REM  Verifica o crea el archivo .env
REM ------------------------------------------------------------
:CHECK_ENV_FILE
if exist "%ROOT%\.env" (
    echo   [OK] Archivo .env encontrado
    call :LOG "CHECK_ENV: OK"
) else (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%ROOT%\.env" >nul 2>&1
        echo   [AVISO] .env no existia - creado desde .env.example
        echo           Edita %ROOT%\.env con tus claves reales
        call :LOG "CHECK_ENV: creado desde .env.example"
    ) else (
        echo   [ERROR] No existe .env ni .env.example
        echo           Crea el archivo .env manualmente
        call :LOG "CHECK_ENV: ERROR - ni .env ni .env.example"
    )
)
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
) else (
    echo   [AVISO] config.json no existe - creando con valores por defecto...
    echo {"max_sql_retries": 4, "enable_auto_correction": true, "log_sql_errors": true, "ai_local_only": true} > "%_CFG%"
    echo   [OK] config.json creado (modo: solo IA local Qwen3 LAN)
    call :LOG "CHECK_CONFIG: creado con valores por defecto"
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
REM Tambien verificar via docker ps si el puerto esta mapeado
for /f "usebackq delims=" %%c in (`docker ps --format "{{.ID}}" 2^>nul`) do (
    docker port %%c 2>nul | findstr ":%_IDC_PID%" >nul 2>&1
)
REM Verificar si el proceso padre es docker
for /f "usebackq delims=" %%r in (`powershell -NoProfile -Command "try { $p = Get-Process -Id %_IDC_PID% -EA Stop; $parent = Get-Process -Id (Get-WmiObject Win32_Process -Filter 'ProcessId=%_IDC_PID%').ParentProcessId -EA Stop; if ($parent.Name -match 'docker') { '1' } else { '0' } } catch { '0' }" 2^>nul`) do (
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
for /f "usebackq tokens=1,2" %%a in (`docker ps --format "%%ID%% %%Names%%" 2^>nul`) do (
    docker port %%a 2>nul | findstr ":%_FDC_PORT%->" >nul 2>&1
    if !errorlevel! equ 0 (
        set "%_FDC_ID_VAR%=%%a"
        set "%_FDC_NAME_VAR%=%%b"
    )
    REM Tambien buscar en formato 0.0.0.0:PORT->
    docker port %%a 2>nul | findstr "%_FDC_PORT%/tcp" >nul 2>&1
    if !errorlevel! equ 0 (
        set "%_FDC_ID_VAR%=%%a"
        set "%_FDC_NAME_VAR%=%%b"
    )
)
REM Metodo alternativo: docker ps con filtro de puerto
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
REM    4. Si es sistema -> avisa y falla
REM ------------------------------------------------------------
:TRY_FREE_PORT
set "_TFP_PORT=%~1"
set "_TFP_RESULT_VAR=%~2"
set "%_TFP_RESULT_VAR%=0"

call :GET_PORT_PID "%_TFP_PORT%" _TFP_PID
if "!_TFP_PID!"=="" (
    REM Puerto ya libre
    set "%_TFP_RESULT_VAR%=1"
    call :LOG "TRY_FREE_PORT %_TFP_PORT%: ya estaba libre"
    goto :EOF
)

call :GET_PROCESS_NAME "!_TFP_PID!" _TFP_PNAME
call :LOG "TRY_FREE_PORT %_TFP_PORT%: ocupado por PID=!_TFP_PID! PROCESO=!_TFP_PNAME!"
echo   Puerto %_TFP_PORT% ocupado por: !_TFP_PNAME! (PID !_TFP_PID!)

REM --- Estrategia 1: Si es Python/uvicorn -> taskkill directo ---
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
    ) else (
        echo   [AVISO] taskkill fallo (puede requerir admin)
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: taskkill Python FALLO"
    )
)

REM --- Estrategia 2: Si es Docker -> docker stop ---
echo !_TFP_PNAME! | findstr /i "docker com.docker wslrelay" >nul 2>&1
if !errorlevel! equ 0 (
    echo   Detectado proceso Docker - buscando contenedor en puerto %_TFP_PORT%...
    call :FIND_DOCKER_CONTAINER_ON_PORT "%_TFP_PORT%" _TFP_CONT_ID _TFP_CONT_NAME
    if not "!_TFP_CONT_ID!"=="" (
        echo   Contenedor encontrado: !_TFP_CONT_NAME! (ID: !_TFP_CONT_ID!)
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
        ) else (
            echo   [ERROR] No se pudo detener el contenedor Docker
            call :LOG "TRY_FREE_PORT %_TFP_PORT%: docker stop FALLO"
        )
    ) else (
        echo   [AVISO] No se encontro el contenedor Docker para el puerto %_TFP_PORT%
        echo   Intentando buscar con docker ps...
        docker ps 2>nul | findstr "%_TFP_PORT%"
        call :LOG "TRY_FREE_PORT %_TFP_PORT%: contenedor Docker no identificado"
    )
)

REM --- Estrategia 3: taskkill generico (ultimo recurso) ---
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
if "!_IPF_PID!"=="" (
    set "%_IPF_VAR%=1"
)
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

REM Puerto ocupado - intentar liberarlo
echo   Puerto %_RP_PREF% ocupado. Intentando liberar...
call :TRY_FREE_PORT "%_RP_PREF%" _RP_FREED
if "!_RP_FREED!"=="1" (
    REM Verificar que realmente quedo libre
    timeout /t 1 /nobreak >nul
    call :IS_PORT_FREE "%_RP_PREF%" _RP_FREE2
    if "!_RP_FREE2!"=="1" (
        echo   [OK] Puerto %_RP_PREF% liberado y disponible
        set "%_RP_VAR%=%_RP_PREF%"
        call :LOG "RESOLVE_PORT: puerto %_RP_PREF% liberado OK"
        goto :EOF
    )
)

REM No se pudo liberar el puerto preferido - buscar alternativo
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

REM Verificar que responde
curl -s --max-time 3 http://localhost:%_WFD_PORT%/health >nul 2>&1
if !errorlevel! neq 0 goto :WAIT_LOOP

REM Verificar que es el DEVIA (buscar "DEVIA" en la respuesta)
for /f "usebackq delims=" %%r in (`curl -s --max-time 3 http://localhost:%_WFD_PORT%/health 2^>nul`) do (
    set "_WFD_RESP=%%r"
)
call :LOG "WAIT_FOR_DEVIA: respuesta health = !_WFD_RESP!"

echo !_WFD_RESP! | findstr /i "DEVIA" >nul 2>&1
if !errorlevel! equ 0 (
    set "%_WFD_VAR%=1"
    goto :EOF
)

REM Responde pero no es el DEVIA
echo   [AVISO] El puerto %_WFD_PORT% responde pero no es el DEVIA:
echo   Respuesta: !_WFD_RESP!
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
REM  :CHECK_DOCKER
REM  Muestra contenedores Docker activos
REM ------------------------------------------------------------
:CHECK_DOCKER
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo   [INFO] Docker no esta corriendo o no esta instalado
    call :LOG "CHECK_DOCKER: Docker no disponible"
    goto :EOF
)
echo   Docker activo. Contenedores corriendo:
docker ps --format "    ID: {{.ID}}  Nombre: {{.Names}}  Puertos: {{.Ports}}" 2>nul
if !errorlevel! neq 0 (
    echo   (ninguno o error al listar)
)
call :LOG "CHECK_DOCKER: OK"
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
) else (
    curl -s --max-time 5 http://jddcia.local/api/vlm/v1/models -H "Authorization: Basic YWRtaW46YWlzdGFjazIwMjY=" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [OK] IA local accesible via jddcia.local
        call :LOG "CHECK_LOCAL_AI: OK via jddcia.local"
    ) else (
        echo   [AVISO] IA local no accesible (192.168.0.36 ni jddcia.local)
        echo   El sistema usara fallback a Groq/Gemini si ai_local_only=false
        call :LOG "CHECK_LOCAL_AI: no accesible"
    )
)
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
) else (
    call :LOG "CHECK_FIREBIRD: OK"
)
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
