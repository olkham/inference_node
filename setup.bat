@echo off
echo InferNode Platform Setup for Windows
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Display Python version
echo Python detected:
python --version
echo.

echo Starting InferNode setup...
echo.

REM Create virtual environment if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
    echo Creating .gitignore in .venv...
    echo * > .venv\.gitignore
) else (
    echo Virtual environment already exists.
)

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Installing/upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing dependencies from requirements.txt...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Warning: Some dependencies may have failed to install
    )
) else (
    echo Warning: requirements.txt not found
)

echo.
echo Installing InferNode in development mode...
pip install -e .
if %errorlevel% neq 0 (
    echo Warning: Failed to install InferNode package
)

echo.
echo Verifying installation...
python -c "from InferenceNode._version import __version__; print('InferNode version: ' + __version__)" 2>nul
if %errorlevel% neq 0 (
    echo Warning: InferNode package verification failed
) else (
    echo [OK] InferNode package installed successfully
)

echo.
echo Setup completed!
echo.
echo IMPORTANT: To use InferNode, activate the virtual environment first:
echo    call .venv\Scripts\activate.bat
echo.
echo Then you can:
echo 1. Start InferNode: python main.py --production
echo 2. Start with custom port: python main.py --port 8080
echo 3. Disable discovery: python main.py --no-discovery
echo 4. Disable telemetry: python main.py --no-telemetry
echo.
echo Web interface will be available at: http://localhost:5555
echo.
echo For Docker deployment, see DOCKER.md or run:
echo    docker-build.bat
echo.
echo To deactivate the virtual environment later, use: deactivate
echo.
pause
