@echo off
rem ---------------------------------------------------------------------
rem  Start IdentifyCollection
rem
rem  Double-click this file to start IdentifyCollection.
rem  It uses the copy of Python inside the "runtime" folder next to it.
rem  Nothing is installed on this computer and no internet is needed.
rem ---------------------------------------------------------------------
setlocal
title IdentifyCollection
cd /d "%~dp0"

if not exist "%~dp0runtime\python.exe" goto not_extracted
if not exist "%~dp0app\launch.py" goto not_extracted

rem Make sure a Python installed elsewhere on this computer cannot interfere.
set "PYTHONHOME="
set "PYTHONPATH="

"%~dp0runtime\python.exe" -I -X utf8 "%~dp0app\launch.py" %*
set "IC_EXIT=%ERRORLEVEL%"
if "%IC_EXIT%"=="0" goto finished

echo.
echo   IdentifyCollection stopped because of a problem (code %IC_EXIT%).
echo   The message above says what happened.
echo.
if "%IDENTIFYCOLLECTION_NO_PAUSE%"=="1" goto finished
echo   Press any key to close this window.
pause >nul
goto finished

:not_extracted
set "IC_EXIT=3"
echo.
echo   IdentifyCollection cannot find its own files.
echo.
echo   This usually means the zip file was opened but not extracted.
echo   Close this window. Then right-click the zip file you downloaded,
echo   choose "Extract All...", and start IdentifyCollection from the
echo   folder that creates.
echo.
if "%IDENTIFYCOLLECTION_NO_PAUSE%"=="1" goto finished
echo   Press any key to close this window.
pause >nul

:finished
endlocal & exit /b %IC_EXIT%
