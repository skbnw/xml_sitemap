# Reuters JP sitemap: CDP 取得 → xml_sitemap へ commit/push
# 用法: Chrome CDP (既定 18800) 起動後に実行
# v1.1 (2026-10-26): pull 前に未コミット変更を stash（workflow ローカル差分で rebase 失敗しない）
# v1.0 (2026-10-26)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent

Set-Location $RepoRoot
$date = (Get-Date).ToUniversalTime().ToString("yyyyMMdd")
$outDir = "rss_reutersjp_$date"

if (-not $env:CHROME_CDP_URL) {
    $env:CHROME_CDP_URL = "http://127.0.0.1:18800"
}

Write-Host "=== Reuters fetch (CDP=$($env:CHROME_CDP_URL)) date=$date ===" -ForegroundColor Cyan

try {
    $r = Invoke-WebRequest -Uri "$($env:CHROME_CDP_URL)/json/version" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -ne 200) { throw "CDP not ready" }
} catch {
    Write-Error "Chrome CDP が応答しません ($($env:CHROME_CDP_URL))。OpenClaw 等で Chrome を起動してください。"
}

$newsDbVenv = "C:\Users\user\Documents\Github\Project_NewsDB\venv\Scripts\python.exe"
$py = if (Test-Path $newsDbVenv) { $newsDbVenv } else { "python" }

& $py (Join-Path $PSScriptRoot "fetch_reutersjp_sitemaps.py") --date $date
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path $outDir)) {
    Write-Error "出力フォルダがありません: $outDir"
}

git add $outDir
if (git diff --cached --quiet) {
    Write-Host "差分なし（本日分は既に commit 済みの可能性）" -ForegroundColor Yellow
    exit 0
}

git commit -m "Add Reuters Japan sitemaps and news sitemaps for $date (CDP local)"

$stashName = "reuters-fetch-push-autostash"
$didStash = $false
$porcelain = git status --porcelain 2>$null
if ($porcelain) {
    git stash push -u -m $stashName | Out-Null
    if ($LASTEXITCODE -eq 0) { $didStash = $true }
}

git pull --rebase origin main
if ($LASTEXITCODE -ne 0) {
    if ($didStash) { git stash pop 2>$null | Out-Null }
    exit $LASTEXITCODE
}

git push origin main
$pushRc = $LASTEXITCODE

if ($didStash) {
    git stash pop 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "stash pop で競合の可能性。git stash list で確認してください。"
    }
}

if ($pushRc -ne 0) { exit $pushRc }
Write-Host "=== push done ===" -ForegroundColor Green
