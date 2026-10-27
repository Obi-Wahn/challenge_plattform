@echo off
rem Startet die Plattform unter Windows: doppelklicken.
rem Die eigentliche Arbeit macht starter.py - diese Datei sucht nur Python.
setlocal
cd /d "%~dp0"

rem Jeder Kandidat wird kurz gestartet, ein Treffer von "where" reicht nicht:
rem Es kann auch ein "py" finden, das die Eingabeaufforderung nicht startet.
rem "py" bringt der Installer von python.org mit. "python" allein kann der
rem leere Platzhalter aus dem Microsoft Store sein, der faellt dabei heraus.
set "PYTHON="
py -3 -c "pass" >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON python -c "pass" >nul 2>nul && set "PYTHON=python"
if not defined PYTHON python3 -c "pass" >nul 2>nul && set "PYTHON=python3"

if not defined PYTHON (
    echo Python wurde nicht gefunden.
    echo Bitte von https://www.python.org/downloads/ installieren und dabei
    echo "Add python.exe to PATH" ankreuzen. Danach diese Datei erneut oeffnen.
    echo.
    pause
    exit /b 1
)

%PYTHON% starter.py %*
if errorlevel 1 (
    echo.
    pause
)
