# push-to-github.ps1
# Run this once to create the BuckClaw GitHub repo and push all 18 steps.
#
# Prerequisites:
#   1. Install Git for Windows: https://git-scm.com/download/win
#   2. Create a GitHub Personal Access Token (classic) with the 'repo' scope:
#      https://github.com/settings/tokens/new
#   3. Run this script from PowerShell:
#      cd <path-to-this-folder>
#      .\push-to-github.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration ────────────────────────────────────────────────────────────
$GitHubUser  = "larrybuckalew"
$RepoName    = "buckclaw"
$RepoDesc    = "BuckClaw: an 18-step progressive tutorial for building a fully-featured AI agent in Python using Anthropic Claude"
$RepoPrivate = $false   # set to $true if you want a private repo

# ── Prompt for token ─────────────────────────────────────────────────────────
$Token = Read-Host "Enter your GitHub Personal Access Token (classic, 'repo' scope)"
if (-not $Token) { Write-Error "Token is required."; exit 1 }

$Headers = @{
    Authorization = "Bearer $Token"
    Accept        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

# ── Create the GitHub repo ────────────────────────────────────────────────────
Write-Host "`nCreating GitHub repo '$GitHubUser/$RepoName'..." -ForegroundColor Cyan

$Body = @{
    name        = $RepoName
    description = $RepoDesc
    private     = $RepoPrivate
    auto_init   = $false
} | ConvertTo-Json

try {
    $Response = Invoke-RestMethod `
        -Uri     "https://api.github.com/user/repos" `
        -Method  POST `
        -Headers $Headers `
        -Body    $Body `
        -ContentType "application/json"
    Write-Host "Repo created: $($Response.html_url)" -ForegroundColor Green
} catch {
    $Status = $_.Exception.Response.StatusCode.value__
    if ($Status -eq 422) {
        Write-Host "Repo already exists -- continuing." -ForegroundColor Yellow
    } else {
        Write-Error "Failed to create repo: $_"
        exit 1
    }
}

# ── Git init, commit, push ────────────────────────────────────────────────────
$ProjectDir = $PSScriptRoot

Write-Host "`nInitializing git repo in: $ProjectDir" -ForegroundColor Cyan

Set-Location $ProjectDir

git init -b main
git config user.email "larry.buckalew@gmail.com"
git config user.name  "Larry Buckalew"

git add -A
git commit -m "Initial commit: BuckClaw -- all 18 steps (00-17)

A progressive tutorial for building a fully-featured AI agent in Python
using Anthropic's Claude API. Steps range from a bare chat loop (00)
through tool calling, event-driven architecture, multi-channel support,
cron jobs, multi-agent dispatch, concurrency control, and long-term
memory (17)."

$RemoteUrl = "https://${GitHubUser}:${Token}@github.com/${GitHubUser}/${RepoName}.git"
git remote remove origin 2>$null
git remote add origin $RemoteUrl
git push -u origin main

Write-Host "`nDone!  Your repo is live at:" -ForegroundColor Green
Write-Host "  https://github.com/$GitHubUser/$RepoName" -ForegroundColor Green
