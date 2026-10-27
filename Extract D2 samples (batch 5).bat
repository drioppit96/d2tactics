@echo off
title D2 Tactics - sample extractor
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python
%PY% tools\extract_samples.py --batch5
