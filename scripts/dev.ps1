<#
.SYNOPSIS
    Start (or restart) both Prompt.ly servers, on Windows.

.DESCRIPTION
    The Windows equivalent of scripts/dev (bash). Same behavior: existing
    listeners on 8000/3000 are freed first, so running this again after
    editing .env doubles as a restart.

.EXAMPLE
    .\scripts\dev.ps1            # start both
.EXAMPLE
    .\scripts\dev.ps1 stop       # stop both
.EXAMPLE
    .\scripts\dev.ps1 backend    # backend only
#>
param(
    [ValidateSet("start", "stop", "backend", "frontend")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $Repo "backend\venv\Scripts\python.exe"
$Logs = Join-Path $Repo ".logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Free-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        Write-Host "  stopping what was on :$port"
        $conns | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 1
    }
}

function Wait-Http($url, $tries, $delayMs) {
    for ($i = 0; $i -lt $tries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Milliseconds $delayMs
    }
    return $false
}

function Start-Backend {
    Free-Port 8000
    if (-not (Test-Path $Py)) {
        Write-Host "  backend venv not found - run .\setup.ps1 first" -ForegroundColor Red
        return $false
    }
    Start-Process -FilePath $Py `
        -ArgumentList "-m", "uvicorn", "backend.main:app", "--port", "8000" `
        -WorkingDirectory $Repo `
        -RedirectStandardOutput (Join-Path $Logs "backend.log") `
        -RedirectStandardError (Join-Path $Logs "backend.err.log") `
        -WindowStyle Hidden

    if (Wait-Http "http://localhost:8000/health" 25 400) {
        Write-Host "  backend  http://localhost:8000  ready"
        $checkLlm = @"
import sys
sys.path.insert(0, r'$Repo')
from backend.llm import available
print('  Claude API: ' + ('enabled' if available() else 'not configured (offline features only)'))
"@
        & $Py -c $checkLlm
        return $true
    }
    Write-Host "  backend failed to start - see $Logs\backend.err.log" -ForegroundColor Red
    Get-Content (Join-Path $Logs "backend.err.log") -Tail 5 -ErrorAction SilentlyContinue
    return $false
}

function Start-Frontend {
    Free-Port 3000
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-Host "  npm not found on PATH - install Node.js first" -ForegroundColor Red
        return $false
    }
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory (Join-Path $Repo "frontend") `
        -RedirectStandardOutput (Join-Path $Logs "frontend.log") `
        -RedirectStandardError (Join-Path $Logs "frontend.err.log") `
        -WindowStyle Hidden

    if (Wait-Http "http://localhost:3000" 40 500) {
        Write-Host "  dashboard  http://localhost:3000  ready"
        return $true
    }
    Write-Host "  dashboard failed to start - see $Logs\frontend.err.log" -ForegroundColor Red
    return $false
}

switch ($Action) {
    "stop"     { Write-Host "Stopping Prompt.ly"; Free-Port 8000; Free-Port 3000 }
    "backend"  { Write-Host "Starting backend";   Start-Backend | Out-Null }
    "frontend" { Write-Host "Starting dashboard";  Start-Frontend | Out-Null }
    default {
        Write-Host "Starting Prompt.ly"
        Start-Backend | Out-Null
        Start-Frontend | Out-Null
        Write-Host "`n  Open http://localhost:3000"
    }
}
