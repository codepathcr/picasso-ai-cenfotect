@echo off
REM Autoprueba: busca, genera una simulacion de colores (256 px), verifica el cache y la regeneracion. Deja log_prueba.txt
cd /d "%~dp0"
set "PY=..\picasso-estilos\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Falta el entorno de Python. Corre primero picasso-estilos\setup_entorno.bat
  pause & exit /b 1
)
if not exist "..\picasso-estilos\data\styles\train" if not exist "..\picasso-estilos\data\muestra\labels.csv" call ..\demo\armar_muestra.bat silencioso
set PYTHONUTF8=1
"%PY%" server.py --selftest > log_prueba.txt 2>&1
type log_prueba.txt
pause
