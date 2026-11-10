@echo off
cd /d "%~dp0"
if not exist outputs mkdir outputs
.venv\Scripts\python -m src.train --model mlp --epochs 30 --workers 2 > outputs\log_mlp.txt 2>&1
.venv\Scripts\python -m src.train --model cnn --epochs 40 --workers 2 > outputs\log_cnn.txt 2>&1
.venv\Scripts\python -m src.train --model resnet18 --epochs 20 --workers 2 > outputs\log_resnet18.txt 2>&1
echo TERMINADO > outputs\FIN.txt
pause
