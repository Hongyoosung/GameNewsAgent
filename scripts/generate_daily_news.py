import os
import sys
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# 새로운 공식 SDK 사용
from google import genai
from google.genai import types

# 1. 환경 변수 및 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TARGET_REPO_PATH = os.environ.get("TARGET_REPO_PATH", ".")
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST)
TODAY_STR = TODAY.strftime("%Y-%m-%d")

if not GEMINI_API_KEY:
    print("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    sys.exit(1)

# 최신 genai 클라이언트 초기화
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = 'gemini-2.5-flash'

# 안전 필터 완화 (기술 문서 요약 시 오탐지 방지 - 새로운 SDK 방식)
safety_settings = [
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
]

def call_gemini(prompt: str, is_json=False) -> str:
    """결제 계정 연동 상태이므로, 대기열(Sleep) 없이 즉각 호출합니다."""
    config_args = {"safety_settings": safety_settings}
    if is_json:
        config_args["response_mime_type"] = "application/json"
        
    config = types.GenerateContentConfig(**config_args)
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        print(f"    ⚠️ Gemini API 호출 오류: {e}")
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
            published_tuple = entry.get('published_parsed', entry.get('updated_parsed'))
            if published_tuple:
                published_dt = datetime(*published_tuple[:6], tzinfo=timezone.utc)
                if published_dt > yesterday:
                    entries.append({
                        "title": entry.title,
                        "link": entry.link,
                        # 본문 추출 실패 시 대비하여 RSS 내 요약본도 수집 (최대 500자)
                        "summary": entry.get('summary', '')[:500] 
                    })
    return entries

def extract_webpage_text(url: str) -> str:
    """URL에서 본문 텍스트 추출 (Reddit 403 방지를 위해 User-Agent 강화)"""
    try:
        # 일반 크롬 브라우저처럼 위장
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        return text[:3000]
    except Exception as e:
        print(f"    ⚠️ 본문 추출 실패 (RSS 요약본으로 대체됨): {e}")
        return ""

def main():
    print(f"🚀 [1/4] RSS 피드 수집 및 기사 선별 시작...")
    rss_entries = fetch_recent_rss_entries()
    
    if not rss_entries:
        print("🚨 최근 24시간 내의 기사가 없습니다.")
        sys.exit(0)

    # 요청 사항: 최대 5개 기사 선별
    rss_text = "\n".join([f"- 제목: {e['title']}\n  링크: {e['link']}\n  요약: {e['summary']}" for e in rss_entries])
    step1_prompt = f"""
    다음은 최근 수집된 뉴스 기사 목록입니다.
    이 중에서 '게임 프로그래밍' 및 'AI/ML 기술'과 관련된 가장 중요한 기사를 **최대 5개** 선별해주세요.
    Unreal/Unity 업데이트, LLM 논문, 그래픽스 최적화 등 기술 중심이어야 하며, 단순 비즈니스나 게임 출시 소식은 제외하세요.
    
    반드시 아래 JSON 형식의 배열로만 응답하세요:
    [
      {{"title": "기사 제목", "link": "기사 URL", "rss_summary": "수집된 요약 내용"}}, ...
    ]
    
    기사 목록:
    {rss_text}
    """
    selected_links_json = call_gemini(step1_prompt, is_json=True)
    selected_articles = json.loads(selected_links_json)
    print(f"    ✅ {len(selected_articles)}개의 기사 선별 완료.")

    print(f"🚀 [2/4] 선별된 기사 본문 추출 및 요약...")
    summaries = []
    for idx, article in enumerate(selected_articles):
        print(f"    📖 분석 중 ({idx+1}/{len(selected_articles)}): {article['title']}")
        content = extract_webpage_text(article['link'])
        
        # 본문(content)이 403 에러로 비어있더라도, RSS 자체 요약(rss_summary)을 주어 유추하게 함
        step2_prompt = f"""
        다음 기사 내용을 분석하여 지정된 형식으로 요약하세요.
        
        제목: {article['title']}
        링크: {article['link']}
        RSS 기본 요약: {article.get('rss_summary', '')}
        본문 내용: {content if content else "(본문을 가져오지 못했습니다. 제목과 링크, RSS 기본 요약을 기반으로 내용을 유추하세요.)"}
        
        형식:
        #### 기사
        링크: [{article['title']}]({article['link']})
        요약: (핵심 기술 내용 1줄)
        영향: (게임/AI 개발 영향 1줄)
        """
        summary = call_gemini(step2_prompt)
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
    
    final_markdown = call_gemini(step3_prompt)
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