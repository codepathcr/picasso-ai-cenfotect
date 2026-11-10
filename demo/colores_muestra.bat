@echo off
REM Motor de colores (Gatys) sobre las obras de muestra, con los modelos reales entrenados (picasso-estilos\outputs\).
REM Genera una grilla de 3 obras x 5 destinos y sus explicaciones en demo\salida\outputs\transfer_muestra\.
cd /d "%~dp0"
set "RAIZ=%~dp0.."
set "EST=%RAIZ%\picasso-estilos"
set "PY=%EST%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Falta el entorno de Python. Corre primero picasso-estilos\setup_entorno.bat
  pause & exit /b 1
)
if not exist "%EST%\data\muestra\labels.csv" call armar_muestra.bat silencioso
set "DATA=%EST%\data\muestra"
set PYTHONUTF8=1
set "PYTHONPATH=%EST%"
if not exist salida\outputs mkdir salida\outputs
cd salida
echo Transfiriendo colores (3 obras x 5 destinos, 400 pasos cada una)...
"%PY%" -m src.style_transfer.transfer --demo --color-content --data "%DATA%" --judge "%EST%\outputs\resnet18.pt" --judge-meta "%EST%\outputs\resnet18.json" --out outputs\transfer_muestra > outputs\log_transfer_muestra.txt 2>&1
echo Escribiendo las explicaciones...
"%PY%" -m src.style_transfer.explain --results outputs\transfer_muestra\results.json --data "%DATA%" > outputs\transfer_muestra\explicaciones.txt 2>&1
echo.
echo Listo. Abre demo\salida\outputs\transfer_muestra\demo_grid.jpg y explicaciones.txt
pause
