@echo off
setlocal

rem Run pytest with output persisted locally so an external caller does not need to
rem hold open Python's stdout/stderr streams.  Launch this script with
rem `cmd /d /c start "" /b ...` when no console window is desired.

set "ROOT=%~dp0.."
set "RUN_DIR=%ROOT%\.local-artifacts\test-runs"
set "PYTHON=%DISTILL_EVERYTHING_PYTHON%"

if "%PYTHON%"=="" if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if "%PYTHON%"=="" set "PYTHON=python"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"

if "%~1"=="" (
    set "PYTEST_ARGS=-q"
) else (
    set "PYTEST_ARGS=%*"
)

pushd "%ROOT%"
"%PYTHON%" -m pytest %PYTEST_ARGS% > "%RUN_DIR%\latest.log" 2>&1
set "RESULT=%ERRORLEVEL%"
popd

> "%RUN_DIR%\latest.exitcode" echo %RESULT%
exit /b %RESULT%
