# GitHub Actions セルフホスト runner（Windows）セットアップ手順
# v1.0 (2026-10-26)
# 1) https://github.com/skbnw/xml_sitemap/settings/actions/runners/new で Windows x64 を選び、表示トークンを控える
# 2) または: gh api -X POST repos/skbnw/xml_sitemap/actions/runners/registration-token --jq .token
# 3) 下記 $RunnerToken に貼り付けて実行（管理者 PowerShell 推奨）

param(
    [Parameter(Mandatory = $true)]
    [string]$RunnerToken,
    [string]$RunnerName = $env:COMPUTERNAME,
    [string]$Labels = "self-hosted,Windows,reuters-cdp"
)

$ErrorActionPreference = "Stop"
$Root = Join-Path $env:USERPROFILE "actions-runner-xml_sitemap"
$Zip = Join-Path $env:TEMP "actions-runner-win-x64.zip"
$Url = "https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-win-x64-2.321.0.zip"

New-Item -ItemType Directory -Force -Path $Root | Out-Null
Invoke-WebRequest -Uri $Url -OutFile $Zip
Expand-Archive -Path $Zip -DestinationPath $Root -Force

Push-Location $Root
.\config.cmd --url "https://github.com/skbnw/xml_sitemap" --token $RunnerToken --name $RunnerName --labels $Labels --unattended
Write-Host "登録完了。サービス化: .\svc.cmd install && .\svc.cmd start" -ForegroundColor Green
Pop-Location
