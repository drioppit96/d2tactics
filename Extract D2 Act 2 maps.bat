@echo off
title D2 Tactics - Act 2 map extractor
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\extract_act.py --act 2
