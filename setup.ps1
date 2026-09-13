<#
.SYNOPSIS
    One-command setup for Prompt.ly on Windows.

.DESCRIPTION
    The Windows equivalent of ./setup (bash). Same five steps, same
    idempotence: every step checks before it acts, so re-running this after
    something drifts repairs it rather than duplicating work.

.PARAMETER NoPath
    Don't touch the user PATH environment variable.
.PARAMETER NoHook
    Skip the auto-import hook.
.PARAMETER NoVSCode
    Skip the VS Code extension.

.EXAMPLE
    .\setup.ps1
.EXAMPLE
    .\setup.ps1 -NoHook
#>
param(
    [switch]$NoPath,
    [switch]$NoHook,
    [switch]$NoVSCode
)

$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Repo "backend\venv"
$BinDir = Join-Path $HOME ".local\bin"

function Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Skip($msg) { Write-Host "[..] $msg" -ForegroundColor DarkGray }
function Warn($msg) { Write-Host "[!!] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "setup: $msg" -ForegroundColor Red; exit 1 }

Write-Host "`nPrompt.ly`n" -ForegroundColor White

# --- 1. interpreter --------------------------------------------------------
# Prefer the `py` launcher (installed by python.org's Windows installer and
# aware of every version on the machine); fall back to a bare `python` for
# Python installed via the Microsoft Store or manually added to PATH.
# Each candidate is (exe, [pre-args]) rather than one flat array, so picking
# the exe apart from its arguments never depends on slicing an array whose
# length varies by candidate - a one-element slice off a one-element array is
# a classic off-by-one in PowerShell's range operator.
$PythonCandidates = @(
    @{ Exe = "py"; PreArgs = @("-3") },
    @{ Exe = "python"; PreArgs = @() }
)
$PythonExe = $null
$PythonPreArgs = $null
foreach ($candidate in $PythonCandidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    $verArgs = $candidate.PreArgs + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
    $ver = & $candidate.Exe @verArgs 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver) {
        $parts = $ver.Trim().Split(".")
        if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 10)) {
            $PythonExe = $candidate.Exe
            $PythonPreArgs = $candidate.PreArgs
            Ok "Python $ver"
            break
        }
    }
}
if (-not $PythonExe) {
    Die "Python 3.10+ not found. Install it from python.org (check 'Add python.exe to PATH') and re-run."
}

# --- 2. virtualenv ----------------------------------------------------------
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (Test-Path $VenvPython) {
    Skip "virtualenv already at backend\venv"
} else {
    & $PythonExe @($PythonPreArgs + @("-m", "venv", $Venv))
    if ($LASTEXITCODE -ne 0) { Die "could not create a virtualenv at $Venv" }
    Ok "created backend\venv"
}

# --- 3. dependencies ---------------------------------------------------------
$Reqs = Join-Path $Repo "backend\requirements.txt"
$Stamp = Join-Path $Venv ".promptly-requirements"
$ReqHash = (Get-FileHash -Algorithm SHA256 $Reqs).Hash

$DepsOk = $false
if ((Test-Path $Stamp) -and ((Get-Content $Stamp -ErrorAction SilentlyContinue) -eq $ReqHash)) {
    & $VenvPython -c "import fastapi, uvicorn, sqlalchemy, dotenv, rich" 2>$null
    if ($LASTEXITCODE -eq 0) { $DepsOk = $true }
}

if ($DepsOk) {
    Skip "dependencies already match backend\requirements.txt"
} else {
    Write-Host "  installing dependencies..."
    & $VenvPython -m pip install --quiet --upgrade pip
    & $VenvPython -m pip install --quiet -r $Reqs
    if ($LASTEXITCODE -ne 0) {
        Die "dependency install failed - re-run '$VenvPython -m pip install -r backend\requirements.txt' to see why"
    }
    Set-Content -Path $Stamp -Value $ReqHash -NoNewline
    Ok "installed everything in backend\requirements.txt"
}

# --- 4. put `promptly` on PATH -----------------------------------------------
# Windows can't run a bare Python file by name and symlinks need elevated
# privileges by default, so instead of linking scripts\promptly.cmd we write a
# tiny wrapper that calls it — same effect, no admin prompt.
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Link = Join-Path $BinDir "promptly.cmd"
$WrapperContent = "@echo off`r`ncall `"$Repo\scripts\promptly.cmd`" %*`r`n"
$NeedsWrite = $true
if (Test-Path $Link) {
    $existing = Get-Content $Link -Raw -ErrorAction SilentlyContinue
    if ($existing -eq $WrapperContent) {
        Skip "promptly already linked into $BinDir"
        $NeedsWrite = $false
    }
}
if ($NeedsWrite) {
    Set-Content -Path $Link -Value $WrapperContent -NoNewline
    Ok "linked promptly -> $BinDir"
}

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$OnPath = $UserPath -and ($UserPath -split ";" | Where-Object { $_.TrimEnd('\') -eq $BinDir.TrimEnd('\') })

if (-not $OnPath) {
    if (-not $NoPath) {
        $NewPath = if ($UserPath) { "$UserPath;$BinDir" } else { $BinDir }
        [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
        Ok "added $BinDir to your PATH (User scope)"
        Warn "open a new terminal before using promptly"
    } else {
        Warn "$BinDir is not on your PATH. Add it in System Properties > Environment Variables, or run:"
        Write-Host "    [Environment]::SetEnvironmentVariable('PATH', `"`$env:PATH;$BinDir`", 'User')"
    }
}

$Promptly = Join-Path $Repo "scripts\promptly.cmd"

# --- 5. import existing history ----------------------------------------------
Write-Host "  importing your Claude Code history..."
& $Promptly sync *> $null
if ($LASTEXITCODE -eq 0) {
    $Totals = & $Promptly projects --json 2>$null
    $Summary = $Totals | & $VenvPython -c @"
import json, sys
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
print(sum(r.get('prompt_count') or 0 for r in rows), len(rows))
"@
    $nPrompts, $nProjects = ($Summary -split '\s+')
    $nPromptsInt = 0
    if ($nPrompts) { [void][int]::TryParse($nPrompts, [ref]$nPromptsInt) }
    if ($nPromptsInt -gt 0) {
        Ok "$nPrompts prompts across $nProjects project(s) scored and ready"
    } else {
        Skip "no Claude Code history found yet - sessions import themselves as you work"
    }
} else {
    Warn "import failed; run 'promptly sync' to see why"
}

# --- 6. auto-import hook ------------------------------------------------------
if (-not $NoHook) {
    & $Promptly install-hook *> $null
    if ($LASTEXITCODE -eq 0) {
        Ok "auto-import hook installed - sessions import themselves"
    } else {
        Warn "could not install the hook; run 'promptly install-hook' to see why"
    }
} else {
    Skip "skipped the auto-import hook"
}

# --- 7. VS Code extension ------------------------------------------------------
# VS Code (and Cursor/VSCodium) use the same ~/.<editor>/extensions layout on
# Windows as everywhere else. Symlinks need Developer Mode or admin rights on
# Windows, so this copies the extension in instead — re-run setup.ps1 after
# updating vscode-extension/ to refresh it.
if (-not $NoVSCode) {
    $anyEditor = $false
    $editors = @{
        "VS Code"          = Join-Path $HOME ".vscode\extensions"
        "VS Code Insiders" = Join-Path $HOME ".vscode-insiders\extensions"
        "Cursor"           = Join-Path $HOME ".cursor\extensions"
        "VSCodium"         = Join-Path $HOME ".vscode-oss\extensions"
    }
    foreach ($label in $editors.Keys) {
        $extDir = $editors[$label]
        if (-not (Test-Path $extDir)) { continue }
        $anyEditor = $true
        $target = Join-Path $extDir "promptly-1.0.0"
        try {
            Copy-Item -Path (Join-Path $Repo "vscode-extension") -Destination $target -Recurse -Force -ErrorAction Stop
            Ok "extension installed in $label - reload the window to see it"
        } catch {
            # A locked file (the editor has it open) shouldn't abort the rest
            # of setup - same best-effort behavior as the bash version.
            Warn "could not copy the extension into $label - $($_.Exception.Message)"
        }
    }
    if (-not $anyEditor) { Skip "no VS Code-family editor found" }
} else {
    Skip "skipped the VS Code extension"
}

# --- done ---------------------------------------------------------------------
Write-Host "`nReady.`n" -ForegroundColor White
Write-Host '  promptly score "your draft"   rate it, and see its token cost, before sending'
Write-Host "  promptly report               how you are prompting in this folder"
Write-Host "  .\scripts\dev.ps1             dashboard at http://localhost:3000`n"
if (-not $OnPath) {
    Write-Host "  Open a new terminal first - PATH was just changed.`n" -ForegroundColor Yellow
}
Write-Host "  promptly doctor checks every part of this setup.`n" -ForegroundColor DarkGray
