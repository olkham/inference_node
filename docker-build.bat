@echo off
echo InferNode Docker Builder
echo =======================
echo.

:menu
echo Choose an option:
echo 1. Build Docker image
echo 2. Run container (basic)
echo 3. Run with docker-compose
echo 4. Stop and remove containers
echo 5. View logs
echo 6. Exit
echo.
set /p choice="Enter choice (1-6): "

if "%choice%"=="1" goto build
if "%choice%"=="2" goto run_basic
if "%choice%"=="3" goto run_compose
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto exit
goto menu

:build
echo Building InferNode Docker image...
docker build -t infernode:latest .
if %errorlevel% neq 0 (
    echo Build failed!
    pause
    goto menu
)
echo Build completed successfully!
pause
goto menu

:run_basic
echo Running InferNode container...
docker run -d --name infernode -p 5000:5000 -p 8888:8888/udp -v "%cd%\InferenceNode\model_repository:/app/InferenceNode/model_repository" -v "%cd%\InferenceNode\logs:/app/InferenceNode/logs" infernode:latest
if %errorlevel% neq 0 (
    echo Failed to start container!
    pause
    goto menu
)
echo Container started! Access at http://localhost:5000
pause
goto menu

:run_compose
echo Starting with docker-compose...
docker-compose up -d
if %errorlevel% neq 0 (
    echo Failed to start with docker-compose!
    pause
    goto menu
)
echo Services started! Access at http://localhost:5000
pause
goto menu

:stop
echo Stopping and removing containers...
docker-compose down
docker stop infernode 2>nul
docker rm infernode 2>nul
echo Containers stopped and removed.
pause
goto menu

:logs
echo Viewing container logs...
docker logs infernode
pause
goto menu

:exit
echo Goodbye!
exit /b 0
