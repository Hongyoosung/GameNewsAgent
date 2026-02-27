#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BASE_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
else
  echo "🚨 .env 파일을 찾을 수 없습니다." >&2
  exit 1
fi

# 한국 시간 기준으로 날짜 설정 (GitHub Actions의 기본 UTC 방지)
export TZ="Asia/Seoul"
DATE="$(date +%F)"
mkdir -p "$BASE_DIR/output"
LOCAL_OUTPUT_FILE="$BASE_DIR/output/${DATE}.md"

if [[ -z "${TARGET_REPO_PATH:-}" ]]; then
  echo "🚨 .env 의 TARGET_REPO_PATH 환경 변수가 설정되어 있지 않습니다." >&2
  exit 1
fi

# Windows Git Bash 환경을 위한 경로 변환
TARGET_REPO_PATH_RAW="$TARGET_REPO_PATH"
if [[ "$TARGET_REPO_PATH_RAW" =~ ^([A-Za-z]):[/\\](.*) ]]; then
  drive_letter="${BASH_REMATCH[1]}"
  rest="${BASH_REMATCH[2]}"
  rest="${rest//\\//}"                      
  drive_letter_lower="${drive_letter,,}"    
  TARGET_REPO_PATH="/mnt/${drive_letter_lower}/${rest}"
else
  TARGET_REPO_PATH="$TARGET_REPO_PATH_RAW"
fi

TARGET_DAILY_DIR="$TARGET_REPO_PATH/content/journal"
TARGET_FILE_NAME="${DATE}_news.ko.md"
TARGET_OUTPUT_FILE="$TARGET_DAILY_DIR/$TARGET_FILE_NAME"

echo "[1/5] OpenClaw 뉴스 수집 및 요약 실행..."

JOB_PROMPT=$(sed "s/{{date}}/$DATE/g" "$BASE_DIR/config/daily-news-job.yaml")

FINAL_MESSAGE="다음 작업 명세서의 지시사항을 수행하고, 최종 결과물 마크다운을 반드시 다음 로컬 경로에 저장해줘: $LOCAL_OUTPUT_FILE

[작업 명세서]
$JOB_PROMPT"

# 3. openclaw 실행 (환경에 맞게 실행 명령어 자동 탐색)
if command -v openclaw &> /dev/null; then
    OPENCLAW_CMD="openclaw"
else
    OPENCLAW_CMD="npx openclaw"
fi

echo "[2/5] 실행..."
# $OPENCLAW_CMD agent --local --agent main --session-id "news-$DATE" --message "$FINAL_MESSAGE"
npx openclaw run "$BASEDIR/config/daily-news-job.yaml" --date "$DATE"

echo "[3/5] 로컬에 생성된 파일 확인..."
if [[ ! -f "$LOCAL_OUTPUT_FILE" ]]; then
  echo "🚨 로컬 output 폴더에 오늘자 MD 파일이 생성되지 않았습니다." >&2
  exit 1
else
  echo "✅ 로컬 파일 생성 확인됨: $LOCAL_OUTPUT_FILE"
fi

echo "[4/5] 블로그 리포지토리로 파일 복사..."
mkdir -p "$TARGET_DAILY_DIR"
cp -f "$LOCAL_OUTPUT_FILE" "$TARGET_OUTPUT_FILE"
echo "✅ 파일 복사 완료: $TARGET_OUTPUT_FILE"

echo "[5/5] GitHub 커밋 및 푸시..."
cd "$TARGET_REPO_PATH"

git add "content/journal/$TARGET_FILE_NAME" || true

if git diff --cached --quiet; then
  echo "변경 사항이 없어 커밋/푸시를 건너뜁니다."
  exit 0
fi

git commit -m "docs: Daily News Update ${DATE}"

retry_count=0
max_retries=3
push_success=false

while [[ $retry_count -lt $max_retries && $push_success == false ]]; do
  if git push origin main; then
    push_success=true
    echo "✅ GitHub 푸시 성공!"
  else
    retry_count=$((retry_count + 1))
    echo "⚠️ Git 푸시 실패. 재시도 중... ($retry_count / $max_retries)"
    sleep 5
  fi
done

if [[ $push_success == false ]]; then
  echo "🚨 3회 재시도에도 불구하고 푸시에 실패했습니다." >&2
  exit 1
fi

cd "$BASE_DIR"
echo "🎉 모든 작업이 성공적으로 완료되었습니다!"