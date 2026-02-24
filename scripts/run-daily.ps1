# 스크립트 실행 위치를 최상단 폴더(gna)로 맞춤
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Split-Path -Parent $ScriptDir
Set-Location $BaseDir

# .env 파일 읽어서 환경 변수로 등록
$EnvFilePath = Join-Path $BaseDir ".env"
if (Test-Path $EnvFilePath) {
    Get-Content $EnvFilePath | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
} else {
    Write-Error "🚨 .env 파일을 찾을 수 없습니다."
    exit 1
}

$TargetRepoPath = $env:TARGET_REPO_PATH
$Date = Get-Date -Format "yyyy-MM-dd"
$LocalOutputFile = Join-Path $BaseDir "output\${Date}.md"
$TargetOutputFile = Join-Path $TargetRepoPath "daily_news\${Date}.md"

Write-Host "[1/6] Docker Compose 시작 및 LLM Warmup 대기..."
docker-compose up -d

# LLM 웜업 대기 (30초)
$timeout = 30
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
$llmReady = $false

while ($stopwatch.Elapsed.TotalSeconds -lt $timeout) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -ErrorAction Stop
        if ($response) {
            $llmReady = $true
            Write-Host "✅ LLM 준비 완료!"
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $llmReady) {
    Write-Error "🚨 LLM warmup 시간 초과 (30초). 작업을 중단합니다."
    docker-compose down
    exit 1
}

Write-Host "[2/6] OpenClaw 뉴스 수집 및 요약 실행..."
docker-compose exec openclaw openclaw run /config/daily-news-job.yaml

Write-Host "[3/6] 로컬(gna)에 생성된 파일 확인..."
if (-not (Test-Path $LocalOutputFile)) {
    Write-Error "🚨 로컬 output 폴더에 오늘자 MD 파일(${Date}.md)이 생성되지 않았습니다."
    docker-compose down
    exit 1
} else {
    Write-Host "✅ 로컬 파일 생성 확인됨."
}

Write-Host "[4/6] Project B로 파일 복사..."
# Project B에 daily_news 폴더가 없다면 생성
$TargetDailyNewsDir = Join-Path $TargetRepoPath "daily_news"
if (-not (Test-Path $TargetDailyNewsDir)) {
    New-Item -ItemType Directory -Path $TargetDailyNewsDir | Out-Null
}

Copy-Item -Path $LocalOutputFile -Destination $TargetOutputFile -Force
Write-Host "✅ 파일 복사 완료: $TargetOutputFile"

Write-Host "[5/6] Project B에서 GitHub 커밋 및 푸시..."
Set-Location $TargetRepoPath

git config user.email "bot@local"
git config user.name "NewsBot"
git add "daily_news/${Date}.md"
git commit -m "Daily News Update ${Date}"

$retryCount = 0
$maxRetries = 3
$pushSuccess = $false

while ($retryCount -lt $maxRetries -and -not $pushSuccess) {
    try {
        git push origin main
        if ($LASTEXITCODE -eq 0) {
            $pushSuccess = $true
            Write-Host "✅ Project B GitHub 푸시 성공!"
        } else {
            throw "Git push exit code was $LASTEXITCODE"
        }
    } catch {
        $retryCount++
        Write-Warning "⚠️ Git 푸시 실패. 재시도 중... ($retryCount / $maxRetries)"
        Start-Sleep -Seconds 5
    }
}

if (-not $pushSuccess) {
    Write-Error "🚨 3회 재시도에도 불구하고 푸시에 실패했습니다."
}

Write-Host "[6/6] VRAM 해제 및 컨테이너 종료..."
Set-Location $BaseDir
docker-compose down
Write-Host "🎉 모든 작업이 성공적으로 완료되었습니다!"