# QRGenPro Build Script for Windows (PowerShell)
# Creates a portable executable using PyInstaller

Write-Host "========================================"
Write-Host "QRGenPro - Build Script (PowerShell)"
Write-Host "========================================"
Write-Host ""

# Check if PyInstaller is installed
$pyinstaller = pip show pyinstaller 2>$null
if (-not $pyinstaller) {
    Write-Host "Installing PyInstaller..."
    pip install pyinstaller
}

Write-Host ""
Write-Host "Building portable executable..."
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Run PyInstaller
pyinstaller --onefile --windowed --name "QRGenPro" --icon="../assets/favicon.ico" "../src/QRGenPro.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Build failed! Check the error messages above." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Executable: dist\QRGenPro.exe"
Write-Host "========================================"
Write-Host ""

# Move the executable to the dist folder in GitHubDocs
if (Test-Path "dist\QRGenPro.exe") {
    Move-Item -Force "dist\QRGenPro.exe" "..\dist\QRGenPro.exe"
    Write-Host "Moved to: ..\dist\QRGenPro.exe" -ForegroundColor Cyan
}

# Cleanup build artifacts
Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
Remove-Item -Force "*.spec" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Build artifacts cleaned up." -ForegroundColor Gray
Read-Host "Press Enter to exit"
