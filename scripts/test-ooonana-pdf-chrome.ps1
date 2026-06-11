Param(
  [string]$Pdf = "docs\ooonana.pdf",
  [string]$Out = "docs\ooonana-pdf-chrome-smoke.png",
  [int]$TimeoutMs = 75000,
  [switch]$KeepProfile,
  [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Help {
  @"
Test Ooonana OS PDF in Chrome.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1
  powershell -ExecutionPolicy Bypass -File scripts/test-ooonana-pdf-chrome.ps1 -TimeoutMs 75000

Output:
  docs\ooonana-pdf-chrome-smoke.png

Notes:
  Uses installed Google Chrome or Microsoft Edge.
  Headless screenshot proves Chromium PDF viewer loads the bootable PDF UI.
"@
}

if ($Help) {
  Show-Help
  exit 0
}

function Find-Browser {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return $candidate
    }
  }
  throw "Chrome/Edge not found"
}

function Resolve-RepoPath([string]$PathValue) {
  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return [System.IO.Path]::GetFullPath($PathValue)
  }
  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
}

$pdfPath = Resolve-RepoPath $Pdf
$outPath = Resolve-RepoPath $Out
if (!(Test-Path -LiteralPath $pdfPath)) {
  throw "PDF not found: $pdfPath"
}

$browser = Find-Browser
$profile = Join-Path $env:TEMP ("ooonana-pdf-chrome-" + [System.Guid]::NewGuid().ToString("N"))
$outDir = Split-Path -Parent $outPath
if ($outDir) {
  New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

$uri = (New-Object System.Uri($pdfPath)).AbsoluteUri
$chromeArgs = @(
  "--headless=new",
  "--disable-gpu",
  "--no-first-run",
  "--no-default-browser-check",
  "--allow-file-access-from-files",
  "--user-data-dir=$profile",
  "--window-size=1280,800",
  "--timeout=$TimeoutMs",
  "--screenshot=$outPath",
  $uri
)

try {
  & $browser @chromeArgs
  $exitCode = 0
  $lastExit = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
  if ($lastExit) {
    $exitCode = [int]$lastExit.Value
  }
  if ($exitCode -ne 0) {
    throw "browser exited $exitCode"
  }
  if (!(Test-Path -LiteralPath $outPath)) {
    throw "screenshot missing: $outPath"
  }
  $size = (Get-Item -LiteralPath $outPath).Length
  if ($size -lt 4000) {
    throw "screenshot too small: $size"
  }
  "ok chrome-pdf $outPath"
}
finally {
  if (!$KeepProfile -and (Test-Path -LiteralPath $profile)) {
    Remove-Item -LiteralPath $profile -Recurse -Force
  }
}
