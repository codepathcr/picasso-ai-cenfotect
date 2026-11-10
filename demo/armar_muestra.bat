@echo off
REM Arma picasso-estilos\data\muestra\ (dataset de DEMOSTRACION) a partir de las 40 pinturas de muestras\pinturas.
cd /d "%~dp0"
set "PY=python"
if exist "..\picasso-estilos\.venv\Scripts\python.exe" set "PY=..\picasso-estilos\.venv\Scripts\python.exe"
%PY% armar_muestra.py
if errorlevel 1 echo Fallo armar_muestra.py
if not "%1"=="silencioso" pause
