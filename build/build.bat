@echo off
REM QRGenPro Build Script for Windows
REM Creates a portable executable using PyInstaller

echo ========================================
echo QRGenPro - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building portable executable...
echo.

cd /d "%~dp0"
pyinstaller --onefile --windowed --name "QRGenPro" --icon="../assets/favicon.ico" "../src/QRGenPro.py"

if errorlevel 1 (
    echo.
    echo Build failed! Check the error messages above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete!
echo Executable: dist\QRGenPro.exe
echo ========================================
echo.

REM Move the executable to the dist folder in GitHubDocs
if exist "dist\QRGenPro.exe" (
    move /Y "dist\QRGenPro.exe" "..\dist\QRGenPro.exe"
    echo Moved to: ..\dist\QRGenPro.exe
)

REM Cleanup build artifacts
rmdir /s /q build 2>nul
del /q *.spec 2>nul
rmdir /s /q dist 2>nul

pause
