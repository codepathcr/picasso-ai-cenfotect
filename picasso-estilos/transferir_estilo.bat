@echo off
cd /d "%~dp0"
del outputs\FIN_TRANSFER.txt 2>nul
.venv\Scripts\python -m src.style_transfer.transfer --demo --color-content --out outputs/transfer_v2 > outputs\log_transfer_v2.txt 2>&1
.venv\Scripts\python -m src.style_transfer.transfer --demo --color-content --judge-weight 0.05 --out outputs/transfer_v2_juez > outputs\log_transfer_v2_juez.txt 2>&1
echo TERMINADO > outputs\FIN_TRANSFER.txt
exit
