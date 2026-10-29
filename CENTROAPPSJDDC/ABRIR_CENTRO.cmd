@echo off
setlocal
pushd "%~dp0"
py -3.12 -c "import tkinter" >nul 2>&1
if errorlevel 1 goto fallback
py -3.12 main.py
goto done
:fallback
python -c "import tkinter; import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 goto missing
python main.py
goto done
:missing
echo Se necesita Python 3.10 o superior con Tkinter. No se ha instalado ni cambiado nada.
pause
popd
exit /b 1
:done
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
popd
exit /b %RESULT%
