@echo off
echo ==========================================
echo 🚀 DEVIA - Sistema de Gestion IA
echo ==========================================
echo.

echo [1/3] Instalando dependencias necesarias...
pip install aiofiles

echo [2/3] Iniciando Servidor Unificado (Backend + Frontend)...
set PYTHONPATH=%CD%
start "DEVIA System" cmd /k "python -m backend.main"

echo [3/3] Abriendo Aplicacion...
timeout /t 5 >nul
start http://localhost:8001

echo.
echo ✅ Sistema iniciado correctamente!
echo - Backend API: http://localhost:8001/docs
echo - Frontend: http://localhost:8001
echo.
echo NOTA: No cierres las ventanas de comandos negras.
echo.
pause
