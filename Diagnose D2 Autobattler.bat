@echo off
title D2 Autobattler - test drive
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
echo The game opens and plays by itself for 3 minutes on a COPY of your heroes.
echo Don't close it. Afterwards, send the file diagnose_report.txt from this folder.
echo.
%PY% tools\diagnose_autobattler.py 180
pause
