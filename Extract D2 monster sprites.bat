@echo off
title D2 Tactics - monster sprite extractor
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\extract_monsters.py
