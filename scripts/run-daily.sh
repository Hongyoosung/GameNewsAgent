#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BASE_DIR" || exit 1

# 1. 환경 변수 로드
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

# 2. 타겟 경로 설정
TARGET_DAILY_DIR="$TARGET_REPO_PATH/content/journal"
TARGET_FILE_NAME="${DATE}_news.ko.md"
TARGET_OUTPUT_FILE="$TARGET_DAILY_DIR/$TARGET_FILE_NAME"

mkdir -p "$TARGET_DAILY_DIR"

if command -v openclaw >/dev/null; then
    OPENCLAW_CMD="openclaw"
else
    OPENCLAW_CMD="npx openclaw"
fi

echo "[1/4] OpenClaw 3스텝 실행 중 (API 제한 대응 및 파이프라인 적용)..."

LINKS_FILE="$TARGET_DAILY_DIR/${DATE}_news-links.txt"
SUMMARIES_FILE="$TARGET_DAILY_DIR/${DATE}_news-summaries.txt"
FINAL_OUTPUT_FILE="$TARGET_OUTPUT_FILE"

# 단일 세션 ID 사용 (모든 스텝이 대화 문맥을 공유하도록)
GLOBAL_SESSION_ID="daily-news-$DATE"

run_step() {
  local step_num=$1
  local prompt_file=$2
  local output_file=$3
  local input_file=$4  # 이전 스텝 결과 파일 경로 (선택)
  
  # 프롬프트 기본 내용 로드 및 날짜 치환
  local step_prompt=$(sed "s/{{date}}/$DATE/g" "$BASE_DIR/config/$prompt_file")

  # 💡 [핵심] 이전 스텝의 결과물이 있다면 프롬프트 뒤에 명시적으로 첨부
  if [[ -n "${input_file:-}" && -f "$input_file" ]]; then
    local previous_result=$(cat "$input_file")
    step_prompt="$step_prompt

[이전 스텝 결과 데이터]
$previous_result"
  fi

  local max_retries=3
  local retry_count=0
  local success=false

  while [[ $retry_count -lt $max_retries && $success == false ]]; do
    echo "  📋 스텝 $step_num 시도 $((retry_count + 1))/$max_retries: $prompt_file → $output_file"
    
    # GLOBAL_SESSION_ID로 통일하여 실행
    if $OPENCLAW_CMD agent --local --agent main \
      --session-id "$GLOBAL_SESSION_ID" \
      --message "$step_prompt" \
      > "$output_file" 2> "${output_file}.log"; then
      
      if grep -qE "429|RESOURCE_EXHAUSTED|rate limit reached|quota exceeded" "${output_file}.log"; then
        echo "    ⚠️ API 할당량 초과 ($((retry_count + 1))회). 120초 후 재시도..."
        retry_count=$((retry_count + 1))
        sleep 122
      else
        echo "    ✅ 스텝 $step_num 성공!"
        success=true
      fi
    else
      echo "    ⚠️ 스텝 $step_num 시스템 오류. 로그 확인: ${output_file}.log"
      retry_count=$((retry_count + 1))
      sleep 122
    fi
  done
  
  if [[ $success == false ]]; then
    echo "🚨 스텝 $step_num 최종 실패. 로그: ${output_file}.log" >&2
    return 1
  fi
}

# 💡 스텝 실행 시 이전 파일($LINKS_FILE, $SUMMARIES_FILE)을 파라미터로 넘겨줌
# 스텝 1: RSS → 링크 목록 (입력 파일 없음)
if ! run_step 1 "rss-links.yaml" "$LINKS_FILE" ""; then exit 1; fi

# 스텝 2: 링크 → 요약 (스텝 1의 LINKS_FILE을 입력으로 사용)
if ! run_step 2 "summarize.yaml" "$SUMMARIES_FILE" "$LINKS_FILE"; then exit 1; fi

# 스텝 3: 요약 → 최종 MD (스텝 2의 SUMMARIES_FILE을 입력으로 사용)
if ! run_step 3 "markdown.yaml" "$FINAL_OUTPUT_FILE" "$SUMMARIES_FILE"; then exit 1; fi

echo "✅ 모든 스텝 완료! 최종 출력: $FINAL_OUTPUT_FILE"

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