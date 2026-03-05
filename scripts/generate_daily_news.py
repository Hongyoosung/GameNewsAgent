import os
import sys
import json
import requests
import feedparser
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

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

# genai 클라이언트 초기화
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = 'gemini-2.5-flash' 

# 안전 필터 설정
safety_settings = [
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
]

def clean_generated_text(text: str) -> str:
    """AI가 생성한 텍스트 정제 및 마크다운 복구"""
    if not text:
        return text
    
    # 1. [P], [R] 등의 불필요한 말머리 제거
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
    """Gemini API 호출 함수"""
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
    """최근 24시간 이내의 고품질 기술 RSS 피드 수집"""
    urls = [
        "https://news.ycombinator.com/rss",                           # Hacker News
        "https://www.reddit.com/r/MachineLearning/new/.rss",          # ML/AI 전문
        "https://www.reddit.com/r/GameDev/new/.rss",                 # 게임 개발 (엔지니어링 중심)
        "https://huggingface.co/feeds/papers.xml",                   # Hugging Face Daily Papers (핵심 AI 논문)
        "https://rss.arxiv.org/rss/cs.GR",                           # ArXiv Graphics (렌더링, 시뮬레이션)
        "https://rss.arxiv.org/rss/cs.AI"                            # ArXiv AI (최신 아키텍처)
    ]
    yesterday = TODAY - timedelta(days=1)
    entries = []

    for url in urls:
        print(f"  📥 RSS 파싱 중: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published_tuple = entry.get('published_parsed', entry.get('updated_parsed'))
                if published_tuple:
                    published_dt = datetime(*published_tuple[:6], tzinfo=timezone.utc)
                    if published_dt > yesterday:
                        entries.append({
                            "title": entry.title,
                            "link": entry.link,
                            "summary": entry.get('summary', '')[:500] 
                        })
        except Exception as e:
            print(f"    ⚠️ RSS 로드 실패 ({url}): {e}")
            
    return entries

def extract_webpage_text(url: str) -> str:
    """URL에서 기술 본문 추출"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 요소 제거
        for script in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        return text[:4000] 
    except Exception as e:
        print(f"    ⚠️ 본문 추출 실패: {e}")
        return ""

def main():
    print(f"🚀 [1/5] 고품질 기술 기사 선별 시작...")
    rss_entries = fetch_recent_rss_entries()
    
    if not rss_entries:
        print("🚨 최근 24시간 내 수집된 기사가 없습니다.")
        sys.exit(0)

    rss_text = "\n".join([f"- 제목: {e['title']}\n  링크: {e['link']}\n  요약: {e['summary']}" for e in rss_entries])
    
    # 기술적 깊이(Low-level, Math, Optimization)를 강조한 선별 프롬프트
    step1_prompt = f"""
    Analyze the following technical articles and select the TOP 10 most significant for 'Game Client Programmers' and 'AI Engineers'.
    
    Selection Criteria:
    1. Technical depth: Focus on C++, GPU architecture, SIMD, Shaders, or LLM internals (Quantization, RAG, Training).
    2. Innovation: New papers from ArXiv or Hugging Face.
    3. Practicality: Real-world optimization or engineering patterns.
    4. Exclude: General business news, simple game reviews, or high-level industry gossip.

    Respond ONLY as a JSON array:
    [
      {{"title": "Article Title", "link": "URL", "rss_summary": "Summary"}}, ...
    ]

    Articles:
    {rss_text}
    """
    
    try:
        selected_links_json = call_gemini(step1_prompt, is_json=True)
        selected_articles = json.loads(selected_links_json)
    except Exception as e:
        print(f"🚨 기사 선별 중 오류 발생: {e}")
        sys.exit(1)
        
    print(f"    ✅ {len(selected_articles)}개의 핵심 기사 선정 완료.")

    print(f"🚀 [2/5] 심층 기술 분석 및 요약")
    summaries = []
    for idx, article in enumerate(selected_articles):
        print(f"    📖 분석 중 ({idx+1}/{len(selected_articles)}): {article['title']}")
        content = extract_webpage_text(article['link'])
        
        step2_prompt = f"""
        Provide a deep technical summary for a senior developer audience.
        Title: {article['title']}
        Link: {article['link']}
        Content: {content if content else "(Use RSS summary and title for context)"}
        
        Format:
        #### Article
        Link: [{article['title']}]({article['link']})
        Summary: (One sentence on the core technical mechanism)
        Impact: (One sentence on how this changes game rendering or AI performance)
        """
        summary = call_gemini(step2_prompt)
        summaries.append(summary)
    
    print(f"🚀 [3/5] 최종 영문 마크다운 포스트 생성...")
    combined_summaries = "\n\n".join(summaries)
    
    step3_en_prompt = f"""
    Today's date is {TODAY_STR}. Write a professional technical blog post.
    Target: Senior Software Engineers.
    
    [Output Format]
    ---
    title: "[Catchy Technical Title]"
    date: {TODAY.strftime("%Y-%m-%dT09:00:00+09:00")}
    draft: false
    description: "[2-3 sentence technical overview]"
    tags: ["Tech", "Engineering", "AI"]
    categories: ["Tech"]
    ---
    
    ### Latest Trends in Game & AI Engineering
    
    (For each article below, expand into 3 points: Core Content, Technical Significance, and Practical Application. Keep it concise.)
    
    {combined_summaries}
    """
    
    final_markdown_en = call_gemini(step3_en_prompt).replace("```markdown", "").replace("```", "").strip()
    final_markdown_en = clean_generated_text(final_markdown_en)

    print(f"🚀 [4/5] 한글 버전 전문가 번역...")
    step4_ko_prompt = f"""
    Translate the following technical blog post into Korean.
    
    [Guidelines]
    1. Tone: Professional and formal (~합니다). Use bullet points for technical details.
    2. Terminology: Keep industry terms like 'Rendering', 'Pipeline', 'Inference', 'Latency', 'Fine-tuning' as is (or transliterate if appropriate).
    3. Maintain all Markdown Frontmatter and links exactly.

    [English Post]
    {final_markdown_en}
    """
    
    final_markdown_ko = call_gemini(step4_ko_prompt).replace("```markdown", "").replace("```", "").strip()
    final_markdown_ko = clean_generated_text(final_markdown_ko)

    print(f"🚀 [5/5] 파일 저장 중...")
    target_dir = os.path.join(TARGET_REPO_PATH, "content", "journal")
    os.makedirs(target_dir, exist_ok=True)
    
    # 영문 저장
    with open(os.path.join(target_dir, f"{TODAY_STR}_news.md"), "w", encoding="utf-8") as f:
        f.write(final_markdown_en)
        
    # 한글 저장
    with open(os.path.join(target_dir, f"{TODAY_STR}_news.ko.md"), "w", encoding="utf-8") as f:
        f.write(final_markdown_ko)
        
    print(f"🎉 성공적으로 저장되었습니다: {target_dir}")

if __name__ == "__main__":
    main()
