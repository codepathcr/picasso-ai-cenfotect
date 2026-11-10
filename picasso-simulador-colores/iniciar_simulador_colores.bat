@echo off
cd /d "%~dp0"
title Simulador Picasso - colores
set "PY=..\picasso-estilos\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Falta el entorno de Python. Corre primero picasso-estilos\setup_entorno.bat
  pause & exit /b 1
)
REM Sin el dataset completo, arma el de demostracion con las 40 pinturas de muestra
if not exist "..\picasso-estilos\data\styles\train" if not exist "..\picasso-estilos\data\muestra\labels.csv" call ..\demo\armar_muestra.bat silencioso
set PYTHONUTF8=1
echo Iniciando el simulador de colores... el navegador se abre en unos segundos.
echo Para detenerlo, cierra esta ventana.
start "" cmd /c "timeout /t 20 >nul & start http://127.0.0.1:8767"
"%PY%" server.py
pause
