@echo off
setlocal
cd /d "%~dp0"

rem --- find Python ---------------------------------------------------------
set "PY=python"
%PY% --version >nul 2>&1 || set "PY=py -3"
%PY% --version >nul 2>&1 || goto :nopython

rem --- install what is missing (prebuilt packages only, nothing is compiled) --
%PY% -c "import pygame, numpy, PIL" >nul 2>&1 && goto :play
echo Installing game libraries, one moment...
%PY% -m pip install --upgrade pip >nul 2>&1
%PY% -m pip install --only-binary=:all: -r requirements.txt
%PY% -c "import pygame, numpy, PIL" >nul 2>&1 || goto :failed

:play
%PY% main.py
if errorlevel 1 (
    echo.
    echo The game stopped with an error. Details are in crash.log in this folder.
    pause
)
exit /b

:nopython
echo Python was not found.
echo Install 64-bit Python 3.12 from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" in the installer, then run this again.
pause
exit /b 1

:failed
echo.
echo Could not install the game libraries for this Python:
%PY% -c "import sys, struct; print('  Python', sys.version.split()[0], str(struct.calcsize('P')*8) + '-bit')"
echo The game needs 64-bit Python 3.10 to 3.13. If yours is older, newer or 32-bit,
echo install 64-bit Python 3.12 from https://www.python.org/downloads/ and run this again.
pause
exit /b 1
