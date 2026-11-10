@echo off
cd /d "%~dp0"
set "PY="
python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (py -3 -c "import sys" >nul 2>&1 && set "PY=py -3")
if not defined PY ( echo No se encontro Python & pause & exit /b 1 )
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -c "import torch;print('CUDA:',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')" > outputs\setup_check.txt 2>&1
type outputs\setup_check.txt
pause
