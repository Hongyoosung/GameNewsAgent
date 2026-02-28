import os
import sys
import json
import requests
import feedparser
import re # 정규표현식 모듈 추가
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

def clean_generated_text(text: str) -> str:
    """AI가 생성한 텍스트에서 불필요한 태그를 제거하고 깨진 마크다운을 복구합니다."""
    if not text:
        return text
        
    # 1. [P], [R] 등의 말머리 태그 제거
    cleaned_text = re.sub(r'\[[A-Z]{1,2}\]\s*', '', text)
    
    # 2. (2 lines) 같은 가이드 문구 제거
    cleaned_text = re.sub(r'\s*\(\d+\s*lines?\)', '', cleaned_text)
    
    # 3. 깨진 마크다운 링크 자동 복구 
    cleaned_text = re.sub(
        r'^(?:###\s*)?(\d+)\.\s*([^\[\n]+?)\s*\((https?://[^\)]+)\)',
        r'### \1. [\2](\3)',
        cleaned_text,
        flags=re.MULTILINE
    )
    
    return cleaned_text

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
    print(f"🚀 [1/5] RSS 피드 수집 및 기사 선별 시작...")
    rss_entries = fetch_recent_rss_entries()
    
    if not rss_entries:
        print("🚨 최근 24시간 내의 기사가 없습니다.")
        sys.exit(0)

    # 요청 사항: 최대 5개 기사 선별
    rss_text = "\n".join([f"- 제목: {e['title']}\n  링크: {e['link']}\n  요약: {e['summary']}" for e in rss_entries])
    step1_prompt = f"""
    Below is a list of recently collected news articles.
    Please select **up to 5** of the most important articles related to "Game Programming" and "AI/ML Technology."
    These articles should be technically focused, such as Unreal/Unity updates, LLM theses, and graphics optimization, and should not include simple business or game release news.

    Please respond only as an array in JSON format:
    [
    {{"title": "Article Title", "link": "Article URL", "rss_summary": "Collected Summary"}}, ...
    ]

    Article List:
    {rss_text}
    """
    selected_links_json = call_gemini(step1_prompt, is_json=True)
    selected_articles = json.loads(selected_links_json)
    print(f"    ✅ {len(selected_articles)}개의 기사 선별 완료.")

    print(f"🚀 [2/5] 선별된 기사 본문 추출 및 요약")
    summaries = []
    for idx, article in enumerate(selected_articles):
        print(f"    📖 분석 중 ({idx+1}/{len(selected_articles)}): {article['title']}")
        content = extract_webpage_text(article['link'])
        
        step2_prompt = f"""
        Analyze the following article content and summarize it in English using the specified format.
        Focus strictly on the technical details relevant to game development and AI engineering.
        
        Title: {article['title']}
        Link: {article['link']}
        RSS Summary: {article.get('rss_summary', '')}
        Content: {content if content else "(Could not fetch content. Infer based on the title, link, and RSS summary.)"}
        
        Format:
        #### Article
        Link: [{article['title']}]({article['link']})
        Summary: (1 sentence of core technical content)
        Impact: (1 sentence on impact for Game/AI development)
        """
        summary = call_gemini(step2_prompt)
        summaries.append(summary)
    
    print(f"🚀 [3/5] 최종 마크다운 블로그 포스트 생성 (영문)...")
    combined_summaries = "\n\n".join(summaries)
    
    # 출력 포맷에서 (2 lines) 등의 문구 제거, 프롬프트 지시사항으로 길이 제한 명시
    step3_en_prompt = f"""
    Today's date is {TODAY_STR}.
    
    Based on the following summarized article data, write a final blog post in English.
    Target audience: 'Game Client Programmers' and 'AI Engineers'.
    
    [Output Format]
    Output ONLY the markdown body for the blog post. Do NOT include extra explanations or markdown code blocks (like ```markdown).
    MUST include actual article URL links.
    Remove any tags like [P], [R], [D] from the article titles.
    
    ---
    title: "[Write a catchy title based on the news - e.g., Unreal C++ Optimization & LLM Trends (Do not include date)]"
    date: {TODAY.strftime("%Y-%m-%dT09:00:00+09:00")}
    draft: false
    description: "[2-3 sentence summary of core tech trends - focus on game dev / AI practical applications]"
    tags: ["Tag1", "Tag2", "Tag3"] # Max 3 tags
    categories: ["Tech"]
    ---
    
    Here are the latest trends in game programming and AI technology.
    
    (Maintain the following format for each article. Keep the descriptions concise, around 2-3 sentences each)
    ### 1. [Actual Article Title Without Tags](Actual Link URL)
    * **Core Content:** ...
    * **Technical Significance:** ...
    * **Practical Application:** ...

    ---

    ### 2. [Actual Article Title Without Tags](Actual Link URL)
    
    [Summarized Data]
    {combined_summaries}
    """
    
    final_markdown_en = call_gemini(step3_en_prompt)
    final_markdown_en = final_markdown_en.replace("```markdown\n", "").replace("```\n", "").strip()
    
    # 정제 함수 적용
    final_markdown_en = clean_generated_text(final_markdown_en)

    print(f"🚀 [4/5] 한글 버전 마크다운 번역 중 (전문가 톤앤매너 적용)...")
    step4_ko_prompt = f"""
    다음은 방금 작성된 영문 기술 블로그 마크다운 포스트입니다.
    이 내용을 한국어 블로그 독자(게임 클라이언트 프로그래머 및 AI 엔지니어)가 자연스럽게 읽을 수 있도록 번역해주세요.

    [번역 톤앤매너 가이드]
    1. 문체: 도입부와 맺음말은 전문적이고 깔끔한 경어체(~합니다, ~습니다)를 사용하고, 각 기사의 요약 항목(핵심 내용, 기술적 의미, 활용 방안)은 간결한 명사형 또는 개조식(~함, ~임)으로 끝맺으세요.
    2. 전문 용어: Rendering, Overhead, Fine-tuning, LLM 등 게임 및 AI 업계에서 흔히 쓰이는 기술 용어는 억지로 한국어로 번역하지 말고 영문 그대로 두거나 익숙한 업계 용어(음역)를 사용하세요.
    3. 어조: 과장된 수식어를 배제하고 객관적이고 기술 중심적인 시각을 유지하세요.

    마크다운 형식(Frontmatter 포함)과 링크는 그대로 유지하고, 본문 내용만 한국어로 번역하세요. Frontmatter의 title과 description도 한국어로 번역해주세요.
    추가 설명이나 마크다운 코드 블록(```markdown 등) 기호는 절대 출력하지 마세요.

    [영문 포스트]
    {final_markdown_en}
    """
    
    final_markdown_ko = call_gemini(step4_ko_prompt)
    final_markdown_ko = final_markdown_ko.replace("```markdown\n", "").replace("```\n", "").strip()
    
    # 정제 함수 한번 더 적용 (번역 과정에서 생길 수 있는 오류 방지)
    final_markdown_ko = clean_generated_text(final_markdown_ko)

    print(f"🚀 [5/5] 파일 저장 중...")
    target_dir = os.path.join(TARGET_REPO_PATH, "content", "journal")
    os.makedirs(target_dir, exist_ok=True)
    
    # 영문 문서 저장 (.md)
    file_name_en = f"{TODAY_STR}_news.md"
    file_path_en = os.path.join(target_dir, file_name_en)
    with open(file_path_en, "w", encoding="utf-8") as f:
        f.write(final_markdown_en)
        
    # 한글 문서 저장 (.ko.md)
    file_name_ko = f"{TODAY_STR}_news.ko.md"
    file_path_ko = os.path.join(target_dir, file_name_ko)
    with open(file_path_ko, "w", encoding="utf-8") as f:
        f.write(final_markdown_ko)
        
    print(f"🎉 성공적으로 두 버전이 생성되었습니다:\n  - {file_path_en}\n  - {file_path_ko}")

if __name__ == "__main__":
    main()