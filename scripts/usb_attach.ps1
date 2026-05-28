# usb_attach.ps1
# --------------
# Attaches the SO-101 USB devices to WSL2 and sets correct permissions.
#
# Run this at the start of every robot session from PowerShell (as admin).
# Without this, /dev/ttyACM0 and /dev/ttyACM1 won't exist in WSL.
#
# Why this exists:
#   USB passthrough to WSL2 is NOT persistent. Every time you unplug or
#   reboot, you have to re-run usbipd attach. We got burned by this enough
#   times that a one-click script became necessary.
#
# Also: the busid can change between sessions (e.g. 3-3 -> 1-5).
#   This script auto-detects the Waveshare board by USB description
#   so you don't have to look it up manually every time.
#
# Usage:
#   Right-click PowerShell -> Run as Administrator
#   cd to this repo
#   .\scripts\usb_attach.ps1
#
# Requirements:
#   usbipd-win installed on Windows (winget install dorssel.usbipd-win)
#   WSL2 running Ubuntu 24.04

Write-Host ""
Write-Host "SO-101 USB Attach Script" -ForegroundColor Cyan
Write-Host "------------------------" -ForegroundColor Cyan
Write-Host ""

# Check usbipd is installed
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] usbipd not found. Install it first:" -ForegroundColor Red
    Write-Host "        winget install --interactive --exact dorssel.usbipd-win"
    exit 1
}

# List all USB devices
$devices = usbipd list 2>&1
Write-Host "Detected USB devices:"
Write-Host $devices
Write-Host ""

# Try to find the Waveshare board automatically
# Shows up as "USB Serial" or "Waveshare" or "STMicroelectronics" depending on driver
$lines = $devices -split "`n"
$robotBusIds = @()

foreach ($line in $lines) {
    if ($line -match "(USB Serial|Waveshare|STM32|ttyACM|STS321)" ) {
        if ($line -match "^(\d+-\d+)") {
            $robotBusIds += $matches[1]
        }
    }
}

if ($robotBusIds.Count -eq 0) {
    Write-Host "[WARN] Could not auto-detect robot USB device." -ForegroundColor Yellow
    Write-Host "       Check the list above and set BUSID manually below."
    Write-Host ""
    # Manual fallback — set your known busid here if auto-detect fails
    $BUSID_FOLLOWER = "1-5"
    $BUSID_LEADER   = ""    # leave empty if only attaching one arm
} else {
    Write-Host "Found $($robotBusIds.Count) candidate device(s): $($robotBusIds -join ', ')" -ForegroundColor Green
    $BUSID_FOLLOWER = $robotBusIds[0]
    $BUSID_LEADER   = if ($robotBusIds.Count -gt 1) { $robotBusIds[1] } else { "" }
}

# Attach follower arm
Write-Host ""
Write-Host "Attaching follower arm (busid: $BUSID_FOLLOWER)..." -ForegroundColor Yellow
usbipd attach --wsl --busid $BUSID_FOLLOWER
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Follower arm attached." -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to attach follower arm. Try binding first:" -ForegroundColor Red
    Write-Host "        usbipd bind --busid $BUSID_FOLLOWER"
}

# Attach leader arm if detected
if ($BUSID_LEADER -ne "") {
    Write-Host ""
    Write-Host "Attaching leader arm (busid: $BUSID_LEADER)..." -ForegroundColor Yellow
    usbipd attach --wsl --busid $BUSID_LEADER
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Leader arm attached." -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Failed to attach leader arm." -ForegroundColor Red
    }
}

# Set permissions inside WSL
Write-Host ""
Write-Host "Setting port permissions in WSL..." -ForegroundColor Yellow
wsl sudo chmod 666 /dev/ttyACM0
if ($BUSID_LEADER -ne "") {
    wsl sudo chmod 666 /dev/ttyACM1
}

# Confirm devices are visible
Write-Host ""
Write-Host "Verifying devices in WSL:" -ForegroundColor Yellow
wsl ls /dev/ttyACM*

Write-Host ""
Write-Host "Done. Run verify_motors.py inside WSL to confirm the arm is ready." -ForegroundColor Cyan
Write-Host ""
Write-Host "    cd ~/lerobot"
Write-Host "    source .venv/bin/activate"
Write-Host "    python ~/lerobot-so101-setup/scripts/verify_motors.py"
Write-Host ""
