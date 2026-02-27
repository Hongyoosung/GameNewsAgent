#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BASE_DIR" || exit 1

# 1. 환경 변수 로드 (GitHub Actions에서 생성한 .env)
if [ -f .env ]; then
    set -a
    . .env
    set +a
else
    echo "🚨 .env 파일이 없습니다." >&2
    exit 1
fi

export TZ="Asia/Seoul"
DATE="$(date +%F)"

if [[ -z "${TARGET_REPO_PATH:-}" ]]; then
  echo "🚨 .env 의 TARGET_REPO_PATH 환경 변수가 설정되어 있지 않습니다." >&2
  exit 1
fi

# 2. 타겟 경로 설정 (불필요한 Windows 경로 변환 제거)
TARGET_DAILY_DIR="$TARGET_REPO_PATH/content/journal"
TARGET_FILE_NAME="${DATE}_news.ko.md"
TARGET_OUTPUT_FILE="$TARGET_DAILY_DIR/$TARGET_FILE_NAME"

# 타겟 디렉토리가 없으면 미리 생성
mkdir -p "$TARGET_DAILY_DIR"

echo "[1/4] OpenClaw 뉴스 수집 및 요약 프롬프트 준비..."
JOB_PROMPT=$(sed "s/{{date}}/$DATE/g" "$BASE_DIR/config/daily-news-job.yaml")

# OpenClaw에게 '타겟 리포지토리' 경로로 바로 저장하라고 지시
FINAL_MESSAGE="다음 작업 명세서의 지시사항을 수행하여 마크다운 본문만 작성해줘:

[작업 명세서]
$JOB_PROMPT"

if command -v openclaw >/dev/null; then
    OPENCLAW_CMD="openclaw"
else
    OPENCLAW_CMD="npx openclaw"
fi

echo "[2/4] OpenClaw 실행 중..."

$OPENCLAW_CMD agent --local --agent main --session-id "news-$DATE" --message "$FINAL_MESSAGE" > "$TARGET_OUTPUT_FILE"

echo "[3/4] 타겟 리포지토리에 생성된 파일 확인..."
if [[ ! -f "$TARGET_OUTPUT_FILE" ]]; then
  echo "🚨 결과물 파일이 생성되지 않았습니다: $TARGET_OUTPUT_FILE" >&2
  exit 1
else
  echo "✅ 파일 생성 완료: $TARGET_OUTPUT_FILE"
fi

echo "[4/4] GitHub 커밋 및 푸시..."
cd "$TARGET_REPO_PATH"

# 새로 생성된 파일을 Git에 추가
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