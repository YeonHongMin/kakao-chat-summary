<#
.SYNOPSIS
KakaoTalk Chat Summarizer (Windows Background Start Script)
Right click this script and select 'Run with PowerShell'
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptPath = $MyInvocation.MyCommand.Path
$projectRoot = Split-Path $scriptPath
Set-Location $projectRoot

Write-Output "🚀 카카오톡 대화 분석기 백그라운드 실행을 준비합니다..."

$existing = Get-CimInstance Win32_Process -Filter "name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*src\app.py*" -or $_.CommandLine -like "*src/app.py*" }

if ($existing) {
    Write-Output "이미 앱이 실행 중입니다. 기존 프로세스를 종료하고 다시 시작합니다."
    $existing | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Seconds 1
}

Start-Process pythonw -ArgumentList "src\app.py"

Write-Output "✅ 실행이 완료되었습니다! 앱 창이나 시스템 트레이를 확인해 주세요."
Start-Sleep -Seconds 3
