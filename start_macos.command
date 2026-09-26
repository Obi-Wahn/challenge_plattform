#!/bin/sh
# Startet die Plattform unter macOS: im Finder doppelklicken.
# Die eigentliche Arbeit macht starter.py - diese Datei sucht nur Python.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 wurde nicht gefunden."
    echo "Bitte von https://www.python.org/downloads/ installieren und diese"
    echo "Datei danach erneut öffnen."
    exit 1
fi

exec python3 starter.py "$@"
