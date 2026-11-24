@echo off
title D2 Autobattler - set up its folder
cd /d "%~dp0"
set PY=py
where py >nul 2>nul || set PY=python

rem Run from the D2 Tactics folder: sets up "Diablo 2 Auto battler" next to it.
if exist "tools\install_autobattler.py" goto here
rem Copied into the (empty) autobattler folder: fills this folder from the D2 Tactics folder beside it.
if exist "..\Diablo 2 Tactics\tools\install_autobattler.py" goto sibling

echo Could not find the D2 Tactics files.
echo Run this file from your "Diablo 2 Tactics" folder (after updating it),
echo or keep it in a folder that sits next to "Diablo 2 Tactics".
goto end

:here
%PY% tools\install_autobattler.py %*
goto end

:sibling
%PY% "..\Diablo 2 Tactics\tools\install_autobattler.py" "%CD%"

:end
pause
