@echo off
cd /d "%~dp0"
del outputs\FIN_DDP.txt 2>nul
del outputs\ddp_init_* 2>nul
for %%W in (1 2 4) do (
  del outputs\ddp_init_%%W 2>nul
  .venv\Scripts\python -m src.distributed.ddp_train --world %%W --epochs 8 > outputs\log_ddp_%%W.txt 2>&1
)
echo TERMINADO > outputs\FIN_DDP.txt
pause
