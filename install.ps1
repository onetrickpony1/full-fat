# Full Fat installer for Windows. No admin rights needed.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/onetrickpony1/full-fat/main/install.ps1 | iex"
#
# What it does:
#   1. installs uv (https://docs.astral.sh/uv/) if missing: it manages Python for Full Fat, and
#      the chat apps use it to start JASP's connector (jasp-mcp)
#   2. installs Full Fat in its own isolated environment, with its own Python if needed
#   3. starts the guided setup (it asks a few plain questions)
# Run it again to update. Uninstall: full-fat uninstall, then uv tool uninstall full-fat

# "Continue": Windows PowerShell turns harmless messages from programs into errors under "Stop";
# every step checks $LASTEXITCODE instead
$ErrorActionPreference = "Continue"
$Source = if ($env:FULL_FAT_SOURCE) { $env:FULL_FAT_SOURCE } else { "full-fat @ https://github.com/onetrickpony1/full-fat/archive/refs/heads/main.zip" }
$Python = if ($env:FULL_FAT_PYTHON) { $env:FULL_FAT_PYTHON } else { "3.12" }

function Say($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
# throw, not exit: when run with "irm ... | iex", exit would close the user's PowerShell window
function Fail($msg) { Write-Host "`nFull Fat installer: $msg" -ForegroundColor Red; throw "Full Fat was not installed" }

Say "Installing Full Fat"

# 1. uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) { $UV = $uv.Source }
else {
    $cand = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $cand)) {
        Say "Installing uv (a Python manager, from astral.sh)"
        try { Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression }
        catch { Fail "could not download uv: $($_.Exception.Message)" }
    }
    if (Test-Path $cand) { $UV = $cand } else { Fail "uv was installed but can't be found; open a new window and run this again" }
}

# 2. Full Fat (+ Python if needed)
Say "Installing Full Fat (Python $Python is downloaded if needed)"
& $UV tool install --force --python $Python $Source
if ($LASTEXITCODE -ne 0) { Fail "installing Full Fat failed (see above)" }
try { & $UV tool update-shell 2>&1 | Out-Null } catch { }
$Bin = (& $UV tool dir --bin).Trim()
$FF = Join-Path $Bin "full-fat.exe"
if (-not (Test-Path $FF)) { Fail "Full Fat was installed but $FF is missing" }
Say ("Installed: " + (& $FF --version))

# 3. guided setup
Say "Setting up"
if ($env:FULL_FAT_SETUP_ARGS) {
    & $FF setup @($env:FULL_FAT_SETUP_ARGS -split " " | Where-Object { $_ })
} else {
    & $FF setup
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSetup stopped before the end. Run the same install line again any time to carry on."
    if ($env:CI) { exit $LASTEXITCODE }
}
