@echo off
REM Add Windows Firewall rules for SSDP Discovery
REM Must be run as Administrator

echo ====================================
echo Configure Firewall for SSDP Discovery
echo ====================================
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires Administrator privileges
    echo Please right-click and select "Run as Administrator"
    echo.
    pause
    exit /b 1
)

echo Adding firewall rules...
echo.

REM Remove old rules if they exist
netsh advfirewall firewall delete rule name="Python SSDP Discovery" >nul 2>&1
netsh advfirewall firewall delete rule name="Python Device HTTP Server" >nul 2>&1

REM Add rule for SSDP (UDP 1900) - Inbound
netsh advfirewall firewall add rule name="Python SSDP Discovery" dir=in action=allow protocol=UDP localport=1900 profile=private,public
if %errorlevel% equ 0 (
    echo [OK] Added inbound rule for UDP port 1900 ^(SSDP^)
) else (
    echo [FAIL] Could not add SSDP rule
)

REM Add rule for HTTP (TCP 8080) - Inbound
netsh advfirewall firewall add rule name="Python Device HTTP Server" dir=in action=allow protocol=TCP localport=8080 profile=private,public
if %errorlevel% equ 0 (
    echo [OK] Added inbound rule for TCP port 8080 ^(HTTP^)
) else (
    echo [FAIL] Could not add HTTP rule
)

REM Also add outbound rules for completeness
netsh advfirewall firewall add rule name="Python SSDP Discovery (Out)" dir=out action=allow protocol=UDP localport=1900 profile=private,public
if %errorlevel% equ 0 (
    echo [OK] Added outbound rule for UDP port 1900 ^(SSDP^)
) else (
    echo [FAIL] Could not add SSDP outbound rule
)

echo.
echo ====================================
echo Firewall configuration complete!
echo ====================================
echo.
echo You can now run win_disco.py
echo.
echo To remove these rules later, run:
echo   netsh advfirewall firewall delete rule name="Python SSDP Discovery"
echo   netsh advfirewall firewall delete rule name="Python Device HTTP Server"
echo   netsh advfirewall firewall delete rule name="Python SSDP Discovery (Out)"
echo.

pause
