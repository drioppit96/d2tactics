@echo off
title D2 Tactics - table extractor
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\extract_tables.py
