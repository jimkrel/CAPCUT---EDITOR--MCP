# PowerShell script chạy UI tests tương đương run_ui_tests.sh
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1. Tạo thư mục tạm
$TempDraftsDir = Join-Path ([System.IO.Path]::GetTempPath()) ("capcut_test_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDraftsDir -Force | Out-Null
Write-Host "[1/4] Tao thu muc test tam: $TempDraftsDir" -ForegroundColor Cyan

# 2. Copy fixture draft sang thư mục tạm
Copy-Item -Path "$ScriptDir\tests\fixtures\sample_draft" -Destination "$TempDraftsDir\sample_draft" -Recurse -Force

$env:CAPCUT_DRAFTS_DIR = $TempDraftsDir
$env:PYTHONUNBUFFERED = "1"

# 3. Khởi động server
Write-Host "[2/4] Khoi dong CapCut Web Studio Server..." -ForegroundColor Cyan
$ServerProc = Start-Process -FilePath "python" -ArgumentList "server.py" -PassThru -NoNewWindow

try {
    # Đợi server sẵn sàng
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/capcut-status" -UseBasicParsing -TimeoutSec 1
            if ($resp.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    
    if (-not $ready) {
        throw "Server khong khoi dong kip tren port 8765!"
    }
    Write-Host "Server da san sang!" -ForegroundColor Green

    # 4. Chạy toàn bộ UI tests
    Write-Host "[3/4] Chay toan bo UI tests..." -ForegroundColor Cyan
    python -m pytest tests/ui/ -v
    $testExitCode = $LASTEXITCODE

    if ($testExitCode -eq 0) {
        Write-Host "=== TAT CA UI TEST DA HOAN THANH XUAT SAC ===" -ForegroundColor Green
    } else {
        Write-Host "Co test that bai!" -ForegroundColor Red
        exit $testExitCode
    }
}
finally {
    Write-Host "[4/4] Don dep tien trinh server va thu muc tam..." -ForegroundColor Yellow
    if ($ServerProc -and -not $ServerProc.HasExited) {
        Stop-Process -Id $ServerProc.Id -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $TempDraftsDir) {
        Remove-Item -Path $TempDraftsDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
