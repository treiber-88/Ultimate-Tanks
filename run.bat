@echo off
cd /d "%~dp0"
python -c "import pygame, numpy, PIL" 2>nul || python -m pip install -r requirements.txt
python main.py
if errorlevel 1 pause
