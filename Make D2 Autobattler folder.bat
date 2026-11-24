@echo off
title D2 Autobattler - set up its folder
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\install_autobattler.py %*
pause
