@echo off
echo InferNode Standalone Launcher
echo =============================
echo.

cd /d "%~dp0"

REM Detect Python executable
set PYTHON_EXE=python
if exist "..\.venv\Scripts\python.exe" (
    set PYTHON_EXE="..\.venv\Scripts\python.exe"
    echo Using virtual environment: .venv
) else if exist "..\venv311\Scripts\python.exe" (
    set PYTHON_EXE="..\venv311\Scripts\python.exe"
    echo Using virtual environment: venv311
) else if exist "..\venv\Scripts\python.exe" (
    set PYTHON_EXE="..\venv\Scripts\python.exe"
    echo Using virtual environment: venv
) else (
    echo No virtual environment found, using system Python
)

:menu
echo.
echo Choose an option:
echo 1. Start with default settings (port 5555)
echo 2. Start with custom port
echo 3. Start with discovery disabled
echo 4. Start with telemetry enabled
echo 5. Custom configuration
echo 6. Exit
echo.
set /p choice="Enter choice (1-6): "

if "%choice%"=="1" goto default
if "%choice%"=="2" goto custom_port
if "%choice%"=="3" goto no_discovery
if "%choice%"=="4" goto with_telemetry
if "%choice%"=="5" goto custom
if "%choice%"=="6" goto exit
goto menu

:default
echo Starting with default settings...
%PYTHON_EXE% inference_node.py
goto end

:custom_port
set /p port="Enter port number (default 5555): "
if "%port%"=="" set port=5555
echo Starting on port %port%...
%PYTHON_EXE% inference_node.py --port %port%
goto end

:no_discovery
echo Starting with discovery disabled...
%PYTHON_EXE% inference_node.py --port 5555 --discovery false
goto end

:with_telemetry
echo Starting with telemetry enabled...
%PYTHON_EXE% inference_node.py --port 5555 --telemetry true
goto end

:custom
set /p port="Enter port (default 5555): "
set /p name="Enter node name (optional): "
set /p discovery="Enable discovery? (true/false, default true): "
set /p telemetry="Enable telemetry? (true/false, default false): "

if "%port%"=="" set port=5555
if "%discovery%"=="" set discovery=true
if "%telemetry%"=="" set telemetry=false

echo Starting with custom configuration...
if "%name%"=="" (
    %PYTHON_EXE% inference_node.py --port %port% --discovery %discovery% --telemetry %telemetry%
) else (
    %PYTHON_EXE% inference_node.py --port %port% --node-name "%name%" --discovery %discovery% --telemetry %telemetry%
)
goto end

:exit
echo Goodbye!
goto end

:end
echo.
echo Press any key to continue...
pause >nul
