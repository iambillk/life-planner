# ================================================================================
# Life Management System - PowerShell Installation Script
# Version: 1.0
# Description: Automated setup for Windows environments using PowerShell
# ================================================================================

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "   LIFE MANAGEMENT SYSTEM - POWERSHELL INSTALLATION" -ForegroundColor Yellow
Write-Host "   Version 1.3.1 - 'Billas Planner 1.0 Beta'" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Function to display progress
function Show-Progress {
    param(
        [int]$Step,
        [int]$Total,
        [string]$Message
    )
    $percent = [math]::Round(($Step / $Total) * 100)
    Write-Progress -Activity "Installing Life Management System" -Status $Message -PercentComplete $percent
    Write-Host "[$Step/$Total] $Message" -ForegroundColor Green
}

$totalSteps = 8
$currentStep = 0

# Check if Python is installed
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Checking Python installation..."
if (!(Test-Command "python")) {
    Write-Host ""
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
$pythonVersion = python --version 2>&1
Write-Host "Python found: $pythonVersion" -ForegroundColor Green
Write-Host ""

# Check if running in project directory
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Verifying project directory..."
if (!(Test-Path "app.py")) {
    Write-Host ""
    Write-Host "ERROR: This script must be run from the project root directory" -ForegroundColor Red
    Write-Host "Please navigate to the life-management-system folder and try again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Project files detected" -ForegroundColor Green
Write-Host ""

# Create virtual environment
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Creating virtual environment..."
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists - skipping creation" -ForegroundColor Yellow
} else {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "Virtual environment created successfully" -ForegroundColor Green
}
Write-Host ""

# Activate virtual environment
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Activating virtual environment..."
& ".\venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "If you see an error about execution policies, run:" -ForegroundColor Yellow
    Write-Host "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Cyan
    Write-Host "Then run this script again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Upgrade pip
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Upgrading pip..."
python -m pip install --upgrade pip --quiet
Write-Host "Pip upgraded to latest version" -ForegroundColor Green
Write-Host ""

# Install requirements
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Installing requirements (this may take a few minutes)..."
Write-Host ""
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to install some requirements" -ForegroundColor Red
    Write-Host "Please check the error messages above" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""
Write-Host "All requirements installed successfully" -ForegroundColor Green
Write-Host ""

# Create necessary directories
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Creating required directories..."
$directories = @(
    "static\uploads",
    "static\uploads\equipment_profiles",
    "static\uploads\maintenance_photos",
    "static\uploads\receipts",
    "static\uploads\property_profiles",
    "static\uploads\property_maintenance",
    "static\uploads\personal_project_files"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created: $dir" -ForegroundColor Gray
    }
}
Write-Host "All directories ready" -ForegroundColor Green
Write-Host ""

# Initialize database
$currentStep++
Show-Progress -Step $currentStep -Total $totalSteps -Message "Initializing database..."
$dbScript = @"
from app import create_app
from models.base import db
app = create_app()
with app.app_context():
    db.create_all()
    from models.daily_planner import init_daily_planner
    init_daily_planner()
    print('Database initialized successfully')
"@

python -c $dbScript
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "WARNING: Database initialization had issues" -ForegroundColor Yellow
    Write-Host "You may need to initialize manually" -ForegroundColor Yellow
}
Write-Host ""

# Complete
Write-Progress -Activity "Installing Life Management System" -Completed
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "   INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Make sure the virtual environment is activated (you should see (venv) in prompt)" -ForegroundColor White
Write-Host "2. Run the application with: " -NoNewline -ForegroundColor White
Write-Host "python app.py" -ForegroundColor Cyan
Write-Host "3. Open your browser to: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:5000" -ForegroundColor Cyan
Write-Host "4. Configure settings at: " -NoNewline -ForegroundColor White
Write-Host "http://localhost:5000/daily/settings" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run the application in the future:" -ForegroundColor Yellow
Write-Host "1. Open PowerShell in project directory" -ForegroundColor White
Write-Host "2. Run: " -NoNewline -ForegroundColor White
Write-Host ".\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "3. Run: " -NoNewline -ForegroundColor White
Write-Host "python app.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Option to start the application now
$response = Read-Host "Would you like to start the application now? (Y/N)"
if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host ""
    Write-Host "Starting Life Management System..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
    Write-Host ""
    python app.py
} else {
    Read-Host "Press Enter to exit"
}