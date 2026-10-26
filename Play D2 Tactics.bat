@echo off
title D2 Tactics
cd /d "%~dp0"

rem use the "py" launcher if it exists, otherwise "python"
set PY=py
where py >nul 2>nul || set PY=python

rem first run: install pygame if it is missing
%PY% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installing pygame, one moment...
    %PY% -m pip install -r requirements.txt
)

%PY% main.py
if errorlevel 1 (
    echo.
    echo Something went wrong - take a screenshot of this window.
    pause
)
