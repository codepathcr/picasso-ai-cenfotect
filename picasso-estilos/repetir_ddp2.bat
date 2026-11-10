@echo off
cd /d "%~dp0"
del outputs\ddp_init_2 2>nul
.venv\Scripts\python -m src.distributed.ddp_train --world 2 --epochs 8 > outputs\log_ddp_2.txt 2>&1
echo TERMINADO > outputs\FIN_DDP2.txt
pause
