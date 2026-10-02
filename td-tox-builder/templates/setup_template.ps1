<#
.SYNOPSIS
    Self-contained, from-zero bootstrap skeleton for a TouchDesigner .tox that
    drives an external Python/conda process.

.DESCRIPTION
    GENERATED FROM: td-tox-builder/templates/setup_template.ps1
    WORKED EXAMPLE: the FluxRT bridge setup script, built in a different
    project - not included in this repository.

    Installs everything UNDER A SINGLE CHOSEN FOLDER (-InstallDir) so nothing
    global is touched and the stack can be deleted by removing that folder. The
    .tox embeds this script and writes it to <InstallDir>\bridge before running it.

    Auto-installs git + git-lfs (winget) and Miniconda if missing. Idempotent.

    ASCII-ONLY ON PURPOSE: Windows PowerShell 5.1 reads unmarked scripts in the
    ANSI codepage; non-ASCII characters (em dashes, box drawing) corrupt the
    parser. Keep this file ASCII-only. (reference.md G5)

.PARAMETER InstallDir
    Folder that holds the whole self-contained stack. Required.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDir,
    [switch]$SkipHeavy
)
$ErrorActionPreference = "Stop"

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$EnvDir    = Join-Path $InstallDir "env"
$BridgeDir = Join-Path $InstallDir "bridge"
$CondaHome = Join-Path $InstallDir "miniconda"
$LockFile  = Join-Path $BridgeDir "requirements.lock.txt"

function Say($m) { Write-Host "[setup] $m" -ForegroundColor Cyan }
function Ok($m)  { Write-Host "[setup] OK  $m" -ForegroundColor Green }
function Die($m) { Write-Host "[setup] ERROR $m" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path $InstallDir, $BridgeDir | Out-Null

# >>> EDIT 1 - hardware preconditions you cannot auto-install (GPU, etc.).
# Example GPU gate (delete if your component is CPU-only):
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Die "NVIDIA GPU/driver not detected. Install the driver and re-run."
}
Ok "GPU present"

# 2. git + git-lfs via winget (with manual fallback message)
$winget = Get-Command winget -ErrorAction SilentlyContinue
function Ensure-Tool($exe, $id, $url) {
    if (Get-Command $exe -ErrorAction SilentlyContinue) { Ok "$exe present"; return }
    if (-not $winget) { Die "$exe missing and winget unavailable. Install: $url" }
    Say "Installing $exe via winget ($id) ..."
    winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [Environment]::GetEnvironmentVariable("Path","User")
    }
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { Die "$exe not on PATH; open a new shell or install: $url" }
    Ok "$exe installed"
}
Ensure-Tool "git"     "Git.Git"       "https://git-scm.com/download/win"
Ensure-Tool "git-lfs" "GitHub.GitLFS" "https://git-lfs.com"
git lfs install | Out-Null

# 3. conda (PATH, else self-contained Miniconda under InstallDir)
function Resolve-Conda {
    if (Get-Command conda -ErrorAction SilentlyContinue) { return "conda" }
    $bat = Join-Path $CondaHome "condabin\conda.bat"
    if (Test-Path $bat) { return $bat }
    return $null
}
$Conda = Resolve-Conda
if (-not $Conda) {
    Say "Installing Miniconda to $CondaHome ..."
    $i = Join-Path $env:TEMP "Miniconda3-latest.exe"
    Invoke-WebRequest "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -OutFile $i
    Start-Process -FilePath $i -Wait -ArgumentList "/InstallationType=JustMe","/RegisterPython=0","/AddToPath=0","/S","/D=$CondaHome"
    Remove-Item $i -ErrorAction SilentlyContinue
    $Conda = Resolve-Conda
    if (-not $Conda) { Die "Miniconda install failed" }
}
Ok "conda: $Conda"

# Accept Anaconda channels' ToS (recent conda blocks env creation otherwise -
# CondaToSNonInteractiveError). Best-effort; older conda lacks `tos`.
foreach ($ch in @("https://repo.anaconda.com/pkgs/main",
                  "https://repo.anaconda.com/pkgs/r",
                  "https://repo.anaconda.com/pkgs/msys2")) {
    try { & $Conda tos accept --override-channels --channel $ch 2>$null | Out-Null } catch {}
}

# Uses $args (no declared param) so short flags like -e / -r pass through
# verbatim instead of being grabbed by PowerShell's parameter binder.
function CondaRun {
    & $Conda run --no-capture-output -p $EnvDir @args
    if ($LASTEXITCODE -ne 0) { throw "failed: $($args -join ' ')" }
}

# 4. prefix env
if (-not (Test-Path (Join-Path $EnvDir "python.exe"))) {
    Say "Creating prefix env (python 3.12) ..."
    # conda-forge + --override-channels sidesteps the Anaconda default-channel ToS gate.
    & $Conda create -p $EnvDir python=3.12 pip -y -c conda-forge --override-channels
}
Ok "prefix env ready"

# >>> EDIT 2 - your pinned dependencies. Reproduce the reference machine via a
# lockfile (pip freeze, filtered). See reference.md "Reproducibility with a lockfile".
if (Test-Path $LockFile) {
    Say "Installing pinned dependencies ..."
    CondaRun pip install -r $LockFile
}
# Example: GPU torch wheels installed from a dedicated index (delete if N/A):
# CondaRun pip install torch==X.Y+cuZZ --index-url https://download.pytorch.org/whl/cuZZ

# >>> EDIT 3 - clone repos / download models / editable installs.
# Example (delete/replace):
# if (-not (Test-Path (Join-Path $InstallDir "Repo\.git"))) {
#     git clone https://github.com/you/Repo (Join-Path $InstallDir "Repo")
# }
# CondaRun pip install -e (Join-Path $InstallDir "Repo")

Ok "Setup complete. Press Start on the component."
