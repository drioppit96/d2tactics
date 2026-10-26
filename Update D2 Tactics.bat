@echo off
title D2 Tactics - updater
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
rem everything runs on one line so this file can be replaced safely while it runs
%PY% tools\update.py & pause & exit /b
