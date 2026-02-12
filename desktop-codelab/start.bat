@echo off
cd /d "%~dp0"
echo Iniciando AI Code Lab...
echo Directrio actual: %CD%

:: Intentar ejecutar npm start (electron .)
call npm start

:: Si falla, intentar invocar node directamente para saltar restricciones
if %errorlevel% neq 0 (
    echo.
    echo 'npm start' fallo. Intentando metodo alternativo directo...
    node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" start
)

if %errorlevel% neq 0 (
    echo.
    echo Hubo un error al iniciar la aplicacion.
    pause
)
