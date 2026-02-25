[#] 한글 깨짐 방지 (출력 인코딩을 UTF-8로 설정)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 스크립트 실행 위치를 리포지토리 루트로 맞춤
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Split-Path -Parent $ScriptDir
Set-Location $BaseDir

Write-Host "[WSL] run-daily.sh 실행 시작..."

# Windows 경로(C:\...)를 WSL 경로(/mnt/c/...)로 변환
if ($BaseDir -match "^[A-Za-z]:\\") {
    $driveLetter = $BaseDir.Substring(0, 1).ToLower()
    $rest = $BaseDir.Substring(2) -replace "\\", "/"
    $WslBaseDir = "/mnt/$driveLetter/$rest"
} else {
    # 이미 WSL 경로이거나 특수한 경우라면 그대로 사용
    $WslBaseDir = $BaseDir
}

wsl bash -lic "cd '$WslBaseDir' && ./scripts/run-daily.sh"

if ($LASTEXITCODE -ne 0) {
    Write-Error "🚨 WSL run-daily.sh 실행 중 오류가 발생했습니다. (exit code: $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "🎉 WSL run-daily.sh 작업이 성공적으로 완료되었습니다!"