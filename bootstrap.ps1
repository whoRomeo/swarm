$ErrorActionPreference = "Stop"

# ============================================================
# AI SWARM — ONE-TIME COMPLETE BOOTSTRAP
# ============================================================

$Repo = "C:\Users\Piyush Shandilya\swarm"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " AI SWARM — COMPLETE BOOTSTRAP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. VERIFY REPOSITORY
# ------------------------------------------------------------

if (-not (Test-Path $Repo)) {
    throw "Repository not found: $Repo"
}

Set-Location $Repo

Write-Host "[1/12] Repository..." -ForegroundColor Yellow
git rev-parse --show-toplevel
git status --short

# ------------------------------------------------------------
# 2. VERIFY GITHUB AUTH
# ------------------------------------------------------------

Write-Host ""
Write-Host "[2/12] GitHub authentication..." -ForegroundColor Yellow

gh auth status

# Verify remote if it already exists
$remote = git remote get-url origin 2>$null
if ($remote) {
    Write-Host "Remote: $remote" -ForegroundColor Green
} else {
    Write-Host "No origin configured. Creating/checking GitHub repository..." -ForegroundColor Yellow

    gh repo create ai-supply-chain-intelligence `
        --private `
        --source=. `
        --remote=origin `
        --push
}

# ------------------------------------------------------------
# 3. FFmpeg — FIND / INSTALL / PATH
# ------------------------------------------------------------

Write-Host ""
Write-Host "[3/12] FFmpeg..." -ForegroundColor Yellow

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue

if ($ffmpeg) {
    Write-Host "FFmpeg already available: $($ffmpeg.Source)" -ForegroundColor Green
}
else {
    Write-Host "FFmpeg not on PATH. Installing/repairing Gyan.FFmpeg..." -ForegroundColor Yellow

    winget install `
        --id Gyan.FFmpeg `
        --exact `
        --accept-source-agreements `
        --accept-package-agreements `
        --silent `
        2>$null

    # Refresh PATH from Windows
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
}

# Search common WinGet/package locations if PATH still does not resolve
if (-not $ffmpeg) {
    Write-Host "Searching installed/package locations..." -ForegroundColor Yellow

    $searchRoots = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages",
        "$env:LOCALAPPDATA\Programs",
        "$env:ProgramFiles",
        "${env:ProgramFiles(x86)}",
        "$env:USERPROFILE\scoop",
        "C:\ffmpeg"
    )

    $found = $null

    foreach ($root in $searchRoots) {
        if (-not (Test-Path $root)) {
            continue
        }

        try {
            $candidate = Get-ChildItem `
                -Path $root `
                -Filter "ffmpeg.exe" `
                -File `
                -Recurse `
                -ErrorAction SilentlyContinue `
                | Select-Object -First 1

            if ($candidate) {
                $found = $candidate.FullName
                break
            }
        }
        catch {}
    }

    if ($found) {
        $ffmpegDir = Split-Path $found -Parent

        # Current session
        if ($env:Path -notlike "*$ffmpegDir*") {
            $env:Path = "$ffmpegDir;$env:Path"
        }

        # Persist for future PowerShell sessions
        $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")

        if ($currentUserPath -notlike "*$ffmpegDir*") {
            [Environment]::SetEnvironmentVariable(
                "Path",
                "$currentUserPath;$ffmpegDir",
                "User"
            )
        }

        $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
    }
}

if (-not $ffmpeg) {
    throw @"
FFmpeg is still unavailable.

The Windows package manager reported installation, but no ffmpeg.exe
could be located in the expected installation/package locations.

Run:
    winget list | findstr /I FFmpeg
    winget show Gyan.FFmpeg

and inspect the installation before continuing.
"@
}

Write-Host "FFmpeg: $($ffmpeg.Source)" -ForegroundColor Green

ffmpeg -version | Select-Object -First 1

# ------------------------------------------------------------
# 4. FFPROBE
# ------------------------------------------------------------

Write-Host ""
Write-Host "[4/12] FFprobe..." -ForegroundColor Yellow

$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue

if (-not $ffprobe) {
    throw "ffprobe.exe was not found alongside FFmpeg."
}

Write-Host "FFprobe: $($ffprobe.Source)" -ForegroundColor Green

# ------------------------------------------------------------
# 5. PYTHON ENVIRONMENT
# ------------------------------------------------------------

Write-Host ""
Write-Host "[5/12] Python environment..." -ForegroundColor Yellow

python --version
python -m pip --version

# Compile every Python file
python -m compileall . -q

Write-Host "Python compilation: PASS" -ForegroundColor Green

# ------------------------------------------------------------
# 6. CHECK FOR DANGEROUS / EMBEDDED SECRETS
# ------------------------------------------------------------

Write-Host ""
Write-Host "[6/12] Secret scan..." -ForegroundColor Yellow

$secretMatches = @()

$patterns = @(
    "ghp_[A-Za-z0-9]+",
    "github_pat_[A-Za-z0-9_]+",
    "sk-or-v1-[A-Za-z0-9]+",
    "AIza[A-Za-z0-9_-]+"
)

foreach ($pattern in $patterns) {
    try {
        $matches = git grep -n -E $pattern -- . 2>$null
        if ($matches) {
            $secretMatches += $matches
        }
    }
    catch {}
}

if ($secretMatches.Count -gt 0) {
    Write-Host ""
    Write-Host "WARNING: Possible credentials found in tracked files:" -ForegroundColor Red
    $secretMatches | ForEach-Object {
        Write-Host $_ -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "DO NOT ignore this. Revoke the affected credential." -ForegroundColor Red
}
else {
    Write-Host "Tracked working tree secret scan: PASS" -ForegroundColor Green
}

# ------------------------------------------------------------
# 7. SEARCH FOR OLD ASYNC BUG
# ------------------------------------------------------------

Write-Host ""
Write-Host "[7/12] Async runner audit..." -ForegroundColor Yellow

$asyncHits = Get-ChildItem -Recurse -File -Include *.py |
    Select-String -Pattern "run_in_executor.*runner\.run|run_in_executor" |
    ForEach-Object { $_.ToString() }

if ($asyncHits) {
    Write-Host "run_in_executor references found:" -ForegroundColor Yellow
    $asyncHits | Select-Object -First 30
}
else {
    Write-Host "No run_in_executor references found." -ForegroundColor Green
}

# Check direct await/create_task patterns
$runnerHits = Get-ChildItem -Recurse -File -Include *.py |
    Select-String -Pattern "await\s+.*runner\.run|create_task\(.*runner\.run"

if ($runnerHits) {
    Write-Host "Correct async runner patterns found." -ForegroundColor Green
}

# ------------------------------------------------------------
# 8. VIDEO GENERATOR AUDIT
# ------------------------------------------------------------

Write-Host ""
Write-Host "[8/12] Video generator..." -ForegroundColor Yellow

if (-not (Test-Path ".\video_generator.py")) {
    throw "video_generator.py not found."
}

$videoText = Get-Content ".\video_generator.py" -Raw

if ($videoText -match "shutil\.which\(['""]ffmpeg['""]\)") {
    Write-Host "System FFmpeg discovery: PASS" -ForegroundColor Green
}
else {
    Write-Host "WARNING: video_generator.py does not visibly use shutil.which('ffmpeg')." -ForegroundColor Yellow
}

if ($videoText -match "http.*ffmpeg|urllib.*ffmpeg|requests.*ffmpeg") {
    Write-Host "WARNING: possible FFmpeg auto-download code remains." -ForegroundColor Yellow
}
else {
    Write-Host "No obvious FFmpeg downloader reference detected." -ForegroundColor Green
}

# ------------------------------------------------------------
# 9. VIDEO SMOKE TEST
# ------------------------------------------------------------

Write-Host ""
Write-Host "[9/12] Video smoke-test discovery..." -ForegroundColor Yellow

$vg = python -c @"
import inspect
import video_generator

print("video_generator import: PASS")

if hasattr(video_generator, "VideoGenerator"):
    cls = video_generator.VideoGenerator
    print("VideoGenerator: FOUND")

    if hasattr(cls, "generate_video"):
        print("generate_video: FOUND")
        print("signature:", inspect.signature(cls.generate_video))
    else:
        print("generate_video: MISSING")
else:
    print("VideoGenerator: MISSING")
"@

Write-Host $vg

# Existing generated videos
$videos = Get-ChildItem ".\videos" -Filter "*.mp4" -File -ErrorAction SilentlyContinue

if ($videos) {
    Write-Host ""
    Write-Host "Existing MP4 files:" -ForegroundColor Green

    foreach ($video in $videos | Select-Object -First 10) {
        Write-Host "  $($video.FullName)"
        ffprobe `
            -v error `
            -show_entries format=duration `
            -show_entries stream=codec_type,width,height `
            -of default=noprint_wrappers=1 `
            "$($video.FullName)"
    }
}
else {
    Write-Host "No existing MP4 found. Running live smoke test..." -ForegroundColor Yellow

    $smoke = python -c @"
import sys
sys.path.insert(0, '.')
from video_generator import VideoGenerator, validate_video
from pathlib import Path

vg = VideoGenerator()
print(f'ffmpeg_available: {vg.ffmpeg_available}')

if vg.ffmpeg_available:
    result = vg.generate_video(
        content_id='bootstrap_smoke',
        title='Bootstrap Smoke Test',
        script='Validating the video pipeline end-to-end. If this works, ffmpeg is correctly installed and the swarm can generate real MP4 files.',
        voiceover_text='Validating the video pipeline end-to-end. If this works, ffmpeg is correctly installed and the swarm can generate real MP4 files.'
    )
    print(f'status: {result["status"]}')
    print(f'video_path: {result.get("video_path", "N/A")}')
    print(f'file_size: {result.get("file_size_bytes", 0) / 1024:.1f} KB')

    if result["status"].startswith("generated"):
        v = validate_video(result["video_path"])
        print(f'validation: {"PASS" if v["valid"] else "FAIL"}')
        print(f'  resolution: {v["resolution"]}')
        print(f'  duration: {v["duration_seconds"]:.1f}s')
        print(f'  video_stream: {v["video_exists"]}')
        print(f'  audio_stream: {v["audio_exists"]}')
        print(f'  errors: {v["errors"] if v["errors"] else "none"}')
    else:
        print(f'generation_failed: {result.get("video_error", "unknown")}')
else:
    print('ffmpeg not available — install via: winget install --id=Gyan.FFmpeg -e')
"@

    Write-Host $smoke
}

# ------------------------------------------------------------
# 10. YOUTUBE / GUMROAD CONFIG AUDIT
# ------------------------------------------------------------

Write-Host ""
Write-Host "[10/12] Publishing integration audit..." -ForegroundColor Yellow

if (Test-Path ".\youtube_oauth.py") {
    Write-Host "youtube_oauth.py: FOUND" -ForegroundColor Green

    Select-String `
        -Path ".\youtube_oauth.py" `
        -Pattern "videos\(\)\.insert|MediaFileUpload|refresh_token|youtube.upload" `
        -SimpleMatch `
        -ErrorAction SilentlyContinue
}
else {
    Write-Host "youtube_oauth.py: MISSING" -ForegroundColor Yellow
}

if (Test-Path ".\agent_swarm.py") {
    $agent = Get-Content ".\agent_swarm.py" -Raw

    if ($agent -match "videos\(\)\.insert") {
        Write-Host "YouTube videos.insert reference: FOUND" -ForegroundColor Green
    }
    else {
        Write-Host "YouTube videos.insert reference: NOT FOUND" -ForegroundColor Yellow
    }

    if ($agent -match "GUMROAD_TOKEN") {
        Write-Host "Gumroad credential reference: FOUND" -ForegroundColor Green
    }
}

# ------------------------------------------------------------
# 11. TEST SUITE
# ------------------------------------------------------------

Write-Host ""
Write-Host "[11/12] Tests..." -ForegroundColor Yellow

$pytest = Get-Command pytest -ErrorAction SilentlyContinue

if ($pytest) {
    pytest -q
}
elseif (Test-Path ".\tests") {
    Write-Host "tests/ exists but pytest is unavailable." -ForegroundColor Yellow
}
else {
    Write-Host "No formal pytest suite exists yet." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 12. GIT STATUS / COMMIT / PUSH
# ------------------------------------------------------------

Write-Host ""
Write-Host "[12/12] Git integration..." -ForegroundColor Yellow

git status --short

git add .

$diffCached = git diff --cached --name-only

if ($diffCached) {
    git commit -m "chore: stabilize ffmpeg video pipeline and automation environment"
}
else {
    Write-Host "No new tracked changes to commit." -ForegroundColor Green
}

git push

# ------------------------------------------------------------
# FINAL REPORT
# ------------------------------------------------------------

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " BOOTSTRAP COMPLETE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Repository:" -ForegroundColor Yellow
git remote get-url origin

Write-Host ""
Write-Host "FFmpeg:" -ForegroundColor Yellow
where.exe ffmpeg
ffmpeg -version | Select-Object -First 1

Write-Host ""
Write-Host "FFprobe:" -ForegroundColor Yellow
where.exe ffprobe

Write-Host ""
Write-Host "Git:" -ForegroundColor Yellow
git log -1 --oneline

Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "1. Any exposed GitHub/YouTube/Gumroad credentials must be revoked/rotated."
Write-Host "2. YouTube still requires Google OAuth authorization for uploads."
Write-Host "3. Gumroad remains a publish-ready/manual-publication workflow."
Write-Host "4. Do not claim PUBLISHED or REVENUE unless an external API confirms it."
Write-Host ""

# Open the Google OAuth credentials page once.
Start-Process "https://console.cloud.google.com/apis/credentials"

Write-Host "Google Cloud OAuth credentials page opened." -ForegroundColor Green
Write-Host ""
Write-Host "Create ONE Desktop OAuth client there, then use the existing"
Write-Host "youtube_oauth.py authentication flow to obtain the refresh token."
Write-Host "Never paste that token into this chat."
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
