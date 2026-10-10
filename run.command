#!/bin/bash
# Ultimate Tanks for macOS - double-click this file in Finder to play.
cd "$(dirname "$0")" || exit 1

pause() { echo; read -n 1 -s -r -p "Press any key to close this window."; echo; }

# --- find Python (64-bit 3.10 to 3.13) ---------------------------------------
PY=""
for c in python3.12 python3.13 python3.11 python3.10 python3 \
         /opt/homebrew/bin/python3 /usr/local/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.1[0-3]/bin/python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    # the python3 that ships with macOS is only a stub until the developer tools are installed
    [ "$p" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1 && continue
    if "$p" -c "import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 13)))" 2>/dev/null; then
        PY="$p"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.10 to 3.13 was not found."
    echo "Install Python 3.12 from https://www.python.org/downloads/ and run this again."
    pause
    exit 1
fi

# --- the game keeps its libraries in its own folder (.venv), nothing else is touched ---
if ! .venv/bin/python -c "import pygame, numpy, PIL" >/dev/null 2>&1; then
    echo "Installing game libraries, one moment..."
    rm -rf .venv
    if "$PY" -m venv .venv; then
        .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
        .venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
    fi
    if ! .venv/bin/python -c "import pygame, numpy, PIL" >/dev/null 2>&1; then
        echo
        echo "Could not install the game libraries for this Python:"
        "$PY" -c "import sys; print('  Python', sys.version.split()[0])"
        echo "Install Python 3.12 from https://www.python.org/downloads/ and run this again."
        pause
        exit 1
    fi
fi

# --- play ---------------------------------------------------------------------
if ! .venv/bin/python main.py; then
    echo
    echo "The game stopped with an error. Details are in crash.log in this folder."
    pause
    exit 1
fi
