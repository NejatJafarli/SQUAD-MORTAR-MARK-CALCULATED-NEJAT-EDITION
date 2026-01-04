# SQUAD Mortar Calculator System Launcher with Map Selection
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "SQUAD Mortar Calculator System" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Available maps
$maps = @(
    "AlBasrah", "Anvil", "Belaya", "BlackCoast", "Chora", "Fallujah",
    "FoolsRoad", "GooseBay", "Gorodok", "Jensen", "Harju", "Kamdesh",
    "Kohat", "Kokan", "Lashkar", "Logar", "Manicouagan", "Mestia",
    "Mutaha", "Narva", "Narva_f", "Pacific", "Sanxian", "Skorpo",
    "Sumari", "Tallil", "Yehorivka"
)

# Display available maps
Write-Host "Available Maps:" -ForegroundColor Yellow
for ($i = 0; $i -lt $maps.Length; $i++) {
    $num = $i + 1
    if ($i % 3 -eq 2) {
        Write-Host ("  {0,2}. {1,-15}" -f $num, $maps[$i])
    } else {
        Write-Host ("  {0,2}. {1,-15}" -f $num, $maps[$i]) -NoNewline
    }
}
Write-Host ""
Write-Host ""

# Get user selection
do {
    $selection = Read-Host "Select map number (1-$($maps.Length)) or type map name"
    
    # Check if input is a number
    if ($selection -match '^\d+$') {
        $index = [int]$selection - 1
        if ($index -ge 0 -and $index -lt $maps.Length) {
            $selectedMap = $maps[$index]
            break
        }
    }
    # Check if input is a map name
    elseif ($maps -contains $selection) {
        $selectedMap = $selection
        break
    }
    
    Write-Host "Invalid selection. Please try again." -ForegroundColor Red
} while ($true)

Write-Host ""
Write-Host "Selected Map: $selectedMap" -ForegroundColor Green
Write-Host ""

Write-Host "Starting Python coordinate reader..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python SmartCordinateMouseOverride.py" -WorkingDirectory $PSScriptRoot

Start-Sleep -Seconds 2

Write-Host "Starting Node.js mortar calculator for $selectedMap..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "node useLegacyMode.js $selectedMap" -WorkingDirectory $PSScriptRoot

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Both systems are now running!" -ForegroundColor Green
Write-Host "Map: $selectedMap" -ForegroundColor Yellow
Write-Host "Close the individual windows to stop them." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to close this launcher"
