# PowerShell script to package the DCS GCI App into a standalone executable using PyInstaller
# Ensure we are in the correct directory
Set-Location -Path $PSScriptRoot\python_gci

# Check if PyInstaller is installed
if (-not (Get-Command "pyinstaller" -ErrorAction SilentlyContinue)) {
    Write-Host "PyInstaller not found. Installing..."
    pip install pyinstaller
}

# Clean old builds
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "app.spec") { Remove-Item "app.spec" -Force }

# Run PyInstaller
Write-Host "Packaging python_gci into GCI_Client.exe..."
# --windowed: Do not show console window
# --onefile: Package into a single .exe
# --name: Output executable name
pyinstaller --windowed --onefile --name GCI_Client app.py

Write-Host "Packaging complete! Executable is located at: $(Resolve-Path .\dist\GCI_Client.exe)"
