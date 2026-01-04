@echo off
echo ==========================================
echo SQUAD Mortar Calculator System
echo ==========================================
echo.
echo Starting Python coordinate reader...
start "Python Coordinate Reader" cmd /k python SmartCordinateMouseOverride.py
timeout /t 2 /nobreak >nul
echo.
echo Starting Node.js mortar calculator...
start "Node.js Mortar Calculator" cmd /k node useLegacyMode.js
echo.
echo ==========================================
echo Both systems are now running!
echo Close this window when you're done.
echo ==========================================
pause
