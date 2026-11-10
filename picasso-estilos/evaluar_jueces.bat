@echo off
cd /d "%~dp0"
.venv\Scripts\python -m src.style_transfer.eval_judges > outputs\log_eval_jueces.txt 2>&1
exit
