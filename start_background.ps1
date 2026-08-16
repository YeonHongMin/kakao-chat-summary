<#
.SYNOPSIS
    카카오톡 대화 분석기 백그라운드 실행 (v2.9.13)

.DESCRIPTION
    pythonw로 GUI 앱을 Cursor와 분리해 실행합니다.
    탐색기에서 우클릭 → "PowerShell로 실행" 또는:
        .\start_background.ps1

.EXAMPLE
    .\start_background.ps1
#>

# Windows PowerShell 5.1 한글/이모지 출력 (UTF-8)
if ($PSVersionTable.PSVersion.Major -lt 6) {
    chcp 65001 | Out-Null
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
Set-Location $projectRoot

Write-Output "[START] 카카오톡 대화 분석기 백그라운드 실행"

# 의존성 확인
python -c "import PySide6, sqlalchemy, hanja" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Output "[INSTALL] 의존성 설치 중..."
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "의존성 설치에 실패했습니다."
        exit 1
    }
}

if (-not (Test-Path ".env.local")) {
    Write-Output "[INFO] .env.local 없음 - env.local.example에서 자동 생성됩니다."
    Write-Output "       상세 분석 전: 도구 -> 설정에서 API 키를 입력하세요."
}

$appArg = "src\app.py"

function Stop-ExistingAppProcesses {
    $existing = Get-CimInstance Win32_Process -Filter "name='python.exe' OR name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*src\app.py*" -or $_.CommandLine -like "*src/app.py*" }

    if ($existing) {
        Write-Output "[STOP] 기존 앱 프로세스 종료"
        $existing | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }
}

Stop-ExistingAppProcesses

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$errLog = Join-Path $logDir "startup_stderr.txt"

Start-Process pythonw -ArgumentList $appArg -WorkingDirectory $projectRoot -RedirectStandardError $errLog

Write-Output "[OK] 백그라운드 실행 완료. 앱 창 또는 시스템 트레이를 확인하세요."
Write-Output "     오류 시: logs\startup_stderr.txt"
