import os
import sys
import time
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# 1. 환경 변수 및 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TARGET_REPO_PATH = os.environ.get("TARGET_REPO_PATH", ".")
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST)
TODAY_STR = TODAY.strftime("%Y-%m-%d")

if not GEMINI_API_KEY:
    print("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
# 최신 Flash 모델 사용 (Gemini 2.5 Flash)
model = genai.GenerativeModel('gemini-2.5-flash')

# 안전 필터 완화 (기술 문서 요약 시 오탐지 방지)
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

def call_gemini_with_retry(prompt: str, is_json=False) -> str:
    """API 호출 제한(429) 등에 대비한 재시도 로직"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            generation_config = {"response_mime_type": "application/json"} if is_json else {}
            response = model.generate_content(
                prompt,
                safety_settings=safety_settings,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            print(f"    ⚠️ Gemini API 호출 오류 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(30 * (attempt + 1)) # 30초, 60초 대기
            else:
                raise

def fetch_recent_rss_entries() -> list:
    """최근 24시간 이내의 RSS 피드 수집"""
    urls = [
        "https://news.ycombinator.com/rss",
        "https://www.reddit.com/r/MachineLearning/new/.rss"
    ]
    yesterday = TODAY - timedelta(days=1)
    entries = []

    for url in urls:
        print(f"  📥 RSS 파싱 중: {url}")
        feed = feedparser.parse(url)
        for entry in feed.entries:
            # RSS 발행 시간 확인 (없는 경우 현재 시간으로 간주)
            published_tuple = entry.get('published_parsed', entry.get('updated_parsed'))
            if published_tuple:
                published_dt = datetime(*published_tuple[:6], tzinfo=timezone.utc)
                if published_dt > yesterday:
                    entries.append({
                        "title": entry.title,
                        "link": entry.link,
                        "summary": entry.get('summary', '')[:200] # 요약본 일부만
                    })
    return entries

def extract_webpage_text(url: str) -> str:
    """URL에서 본문 텍스트 추출 (OpenClaw의 xurl 역할 대체)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 태그 제거
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        return text[:3000] # 토큰 제한을 위해 앞부분 3000자만 추출
    except Exception as e:
        print(f"    ⚠️ {url} 본문 추출 실패: {e}")
        return ""

def main():
    print(f"🚀 [1/4] RSS 피드 수집 및 기사 선별 시작...")
    rss_entries = fetch_recent_rss_entries()
    
    if not rss_entries:
        print("🚨 최근 24시간 내의 기사가 없습니다.")
        sys.exit(0)

    # Step 1: 기사 선별 (JSON 응답 강제)
    rss_text = "\n".join([f"- 제목: {e['title']}\n  링크: {e['link']}\n  요약: {e['summary']}" for e in rss_entries])
    step1_prompt = f"""
    다음은 최근 수집된 뉴스 기사 목록입니다.
    이 중에서 '게임 프로그래밍' 및 'AI/ML 기술'과 관련된 가장 중요한 기사를 **최대 3개만** 선별해주세요.
    Unreal/Unity 업데이트, LLM 논문, 그래픽스 최적화 등 기술 중심이어야 하며, 단순 비즈니스나 게임 출시 소식은 제외하세요.
    
    반드시 아래 JSON 형식의 배열로만 응답하세요:
    [
      {{"title": "기사 제목", "link": "기사 URL"}}, ...
    ]
    
    기사 목록:
    {rss_text}
    """
    selected_links_json = call_gemini_with_retry(step1_prompt, is_json=True)
    selected_articles = json.loads(selected_links_json)
    print(f"    ✅ {len(selected_articles)}개의 기사 선별 완료.")

    print(f"🚀 [2/4] 선별된 기사 본문 추출 및 요약...")
    summaries = []
    for article in selected_articles:
        print(f"    📖 분석 중: {article['title']}")
        content = extract_webpage_text(article['link'])
        
        step2_prompt = f"""
        다음 기사 내용을 분석하여 지정된 형식으로 요약하세요.
        
        제목: {article['title']}
        링크: {article['link']}
        본문 내용: {content if content else "(본문을 가져오지 못했습니다. 제목과 링크 기반으로 유추하세요.)"}
        
        형식:
        #### 기사
        링크: [{article['title']}]({article['link']})
        요약: (핵심 기술 내용 1줄)
        영향: (게임/AI 개발 영향 1줄)
        """
        summary = call_gemini_with_retry(step2_prompt)
        summaries.append(summary)
    
    print(f"🚀 [3/4] 최종 마크다운 블로그 포스트 생성...")
    combined_summaries = "\n\n".join(summaries)
    step3_prompt = f"""
    오늘 날짜는 {TODAY_STR}입니다.
    
    다음 요약된 기사 데이터를 바탕으로 최종 블로그 포스트를 작성하세요.
    타깃 독자: '게임 클라이언트 프로그래머' 및 'AI 엔지니어'.
    
    [출력 형식]
    블로그 포스팅용 마크다운 본문만 출력. 추가 설명/코드블록(```markdown 등) 금지.
    실제 기사 URL 링크 필수.
    
    ---
    title: "[수집된 뉴스를 바탕으로 매력적인 제목 작성 - 예: {TODAY_STR} Unreal C++ 최적화 & LLM 트렌드]"
    date: {TODAY.strftime("%Y-%m-%dT09:00:00+09:00")}
    draft: false
    description: "[핵심 기술 동향 2-3줄 요약 - 게임 개발/AI 실무 적용 포인트 중심]"
    tags: ["News", "Game Programming", "AI Trends", "Tech"]
    categories: ["Tech"]
    ---
    
    최신 게임 프로그래밍 및 AI 기술 동향을 전해드립니다.
    
    (이후 각 기사별로 아래 형식 유지)
    #### 1. [실제 기사 제목](실제 링크 URL)
    * **핵심 내용:** ...
    * **기술적 의미:** ...
    * **활용 방안:** ...
    
    [요약 데이터]
    {combined_summaries}
    """
    
    final_markdown = call_gemini_with_retry(step3_prompt)
    
    # 마크다운 코드블록 마커가 섞여 들어올 경우 제거
    final_markdown = final_markdown.replace("```markdown\n", "").replace("```\n", "").strip()

    print(f"🚀 [4/4] 파일 저장 중...")
    target_dir = os.path.join(TARGET_REPO_PATH, "content", "journal")
    os.makedirs(target_dir, exist_ok=True)
    
    file_name = f"{TODAY_STR}_news.ko.md"
    file_path = os.path.join(target_dir, file_name)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_markdown)
        
    print(f"🎉 성공적으로 생성되었습니다: {file_path}")

if __name__ == "__main__":
    main()