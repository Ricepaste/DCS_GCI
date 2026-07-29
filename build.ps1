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

# Run PyInstaller (--onedir avoids Windows Defender false positive malware flags)
Write-Host "Packaging python_gci into GCI_Client directory..."
pyinstaller --windowed --onedir --name GCI_Client --collect-all mgrs --collect-all pyproj --add-data "map_data;map_data" --add-data "airspaces_config.json;." app.py

# Ensure map_data and airspaces_config.json are copied into dist\GCI_Client
if (Test-Path "map_data") {
    Copy-Item -Path "map_data" -Destination "dist\GCI_Client\map_data" -Recurse -Force
}
if (Test-Path "airspaces_config.json") {
    Copy-Item -Path "airspaces_config.json" -Destination "dist\GCI_Client\airspaces_config.json" -Force
}

# Compress output folder to ZIP
Write-Host "Compressing to GCI_Client.zip..."
if (Test-Path "dist\GCI_Client.zip") { Remove-Item "dist\GCI_Client.zip" -Force }
Compress-Archive -Path "dist\GCI_Client\*" -DestinationPath "dist\GCI_Client.zip" -Force

Write-Host "Packaging complete! Zip package is located at: $(Resolve-Path .\dist\GCI_Client.zip)"
