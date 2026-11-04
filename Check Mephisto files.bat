@echo off
title D2 Tactics - Mephisto file check
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\check_unit.py MP
pause
