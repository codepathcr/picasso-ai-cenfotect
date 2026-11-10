@echo off
REM Reentrena los clasificadores y el DDP con las 40 pinturas de muestra (prueba de que el entrenamiento corre de punta a punta).
REM Los resultados van a demo\salida\outputs\ : NO toca los modelos reales de picasso-estilos\outputs\.
REM Con 20 imagenes de entrenamiento el acierto no significa nada; los resultados reales estan en picasso-estilos\outputs\.
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
echo [1/4] MLP...
"%PY%" -m src.train --model mlp --data "%DATA%" --epochs 10 --workers 0 > outputs\log_mlp.txt 2>&1
echo [2/4] CNN...
"%PY%" -m src.train --model cnn --data "%DATA%" --epochs 10 --workers 0 > outputs\log_cnn.txt 2>&1
echo [3/4] ResNet18...
"%PY%" -m src.train --model resnet18 --data "%DATA%" --epochs 5 --workers 0 > outputs\log_resnet18.txt 2>&1
echo [4/4] Entrenamiento distribuido (DDP, 2 procesos)...
"%PY%" -m src.distributed.ddp_train --world 2 --epochs 2 --data "%DATA%" > outputs\log_ddp_2.txt 2>&1
echo.
echo Listo. Revisa demo\salida\outputs\ (log_*.txt, *.json).
pause
