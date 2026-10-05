$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/akashgagda/hermes-one-piece-profiles.git"
if ($env:HERMES_ONE_PIECE_HOME) {
    $Checkout = $env:HERMES_ONE_PIECE_HOME
} else {
    $Checkout = Join-Path $env:LOCALAPPDATA "hermes-one-piece-profiles"
}

foreach ($Command in @("git", "python", "hermes")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$Command is required."
    }
}

if (Test-Path (Join-Path $Checkout ".git")) {
    Write-Host "Using existing checkout at $Checkout (not pulling code automatically)."
} elseif (Test-Path $Checkout) {
    throw "$Checkout exists but is not this collection's git checkout."
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $Checkout) | Out-Null
    & git clone --depth 1 $RepoUrl $Checkout
}

& python (Join-Path $Checkout "manage.py") install @args
exit $LASTEXITCODE
