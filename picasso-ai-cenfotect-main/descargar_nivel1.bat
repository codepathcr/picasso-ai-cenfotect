@echo off
REM Descarga Nivel 1 del proyecto Picasso (catalogo + imagenes + contexto). Reanudable.
cd /d "%~dp0"

set "PY="
python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (py -3 -c "import sys" >nul 2>&1 && set "PY=py -3")
if not defined PY (
  echo No se encontro Python. Instalalo desde python.org marcando "Add python.exe to PATH".
  pause & exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  echo Se creo .env: abrelo, escribe PICASSO_USER y PICASSO_PASS, guarda y vuelve a ejecutar este script.
  pause & exit /b 1
)

echo Usando Python: %PY%
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv || (echo Fallo al crear el venv & pause & exit /b 1)
  .venv\Scripts\python -m pip install -r requirements.txt || (echo Fallo al instalar dependencias & pause & exit /b 1)
)
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m src.etl.run_pipeline --phase all --no-popups --resume
if %ERRORLEVEL%==2 echo BLOQUEO/CAPTCHA detectado: no reintentar, avisar.
.venv\Scripts\python -m src.etl.run_pipeline --phase load
pause
