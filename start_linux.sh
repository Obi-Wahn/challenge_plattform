#!/bin/sh
# Startet die Plattform unter Linux: im Terminal ./start_linux.sh
# Die eigentliche Arbeit macht starter.py - diese Datei sucht nur Python.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 wurde nicht gefunden."
    echo "Unter Debian und Ubuntu: sudo apt install python3 python3-venv"
    exit 1
fi

exec python3 starter.py "$@"
