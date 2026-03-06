@echo off
REM ============================================================
REM  DEVIA Chat API - Script de inicio
REM  Servidor: 0.0.0.0:8001
REM  BD Firebird: 192.168.0.254:3050 (HOST1.JDDC.local)
REM  Uso: doble clic o ejecutar desde CMD o PowerShell
REM ============================================================

cd /d "%~dp0"
echo.
echo ============================================================
echo  DEVIA Chat API - Iniciando...
echo  Directorio: %CD%
echo  Puerto: 8001
echo  BD: 192.168.0.254:3050
echo ============================================================
echo.

REM Verificar que el venv existe
if not exist ".venv\Scripts\uvicorn.exe" (
    echo ERROR: No se encuentra .venv\Scripts\uvicorn.exe
    echo Ejecuta: python -m venv .venv
    echo Luego:   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Matar proceso anterior en puerto 8001 si existe
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    echo Matando proceso anterior en puerto 8001 (PID %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

REM Establecer PYTHONPATH al directorio actual
set PYTHONPATH=%CD%

echo Iniciando uvicorn en puerto 8001...
echo Chat web: http://localhost:8001
echo Health:   http://localhost:8001/health
echo API docs: http://localhost:8001/docs
echo.
.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8001 --log-level info

pause
