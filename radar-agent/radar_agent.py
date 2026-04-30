import os
import json
import time
import requests
import feedparser
from urllib.parse import quote

# ================= 配置与环境变量 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CF_WORKER_URL = os.environ.get("CF_WORKER_URL")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "SPEC-2026-SuperSecretKey")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# ================= 核心功能引擎 =================
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def universal_fetcher(source_name, target_url):
    try:
        response = requests.get(target_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        entries = feedparser.parse(response.content).entries
        return [{
            "title": e.title, 
            "content": getattr(e, 'summary', getattr(e, 'description', '')), 
            "url": getattr(e, 'link', ''), 
            "source": source_name
        } for e in entries]
    except Exception as e:
        print(f"  └─ ❌ [抓取失败] {e}")
        return []

def analyze_with_gemma(title, content, source):
    """切换回 Gemma 4 31B 引擎"""
    if not GEMINI_API_KEY: return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    You are an AI analyst. Output ONLY strict JSON.
    Context: {source} | Title: {title}
    Text: {content[:1000]}
    
    JSON Structure:
    {{
        "summary": "50字内中文摘要",
        "tags": "3个英文标签",
        "importance_score": 1-10,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话价值描述"
    }}
    """

    try:
        # Gemma 31B 比较慢，timeout 给够 60 秒
        resp = requests.post(
            url, 
            json={"contents": [{"parts": [{"text": prompt}]}]}, 
            timeout=60
        )
        
        if resp.status_code != 200:
            print(f"  └─ ❌ [API错误] {resp.status_code}")
            return None

        raw_text = resp.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        # 极简清洗
        cleaned_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("
```").strip()
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"  └─ ⚠️ [AI异常] {e}")
        return None

# ================= 主控制流 =================
def main():
    config = load_config()
    all_raw_data = []
    print("\n⚡ 极速测试模式启动...\n")

    for source in config.get("sources", []):
        for interest in config.get("interests", []):
            if interest["id"] == "trending":
                target_url = source["trending_url"]
            else:
                target_url = source["search_url"].replace("{keyword}", quote(interest["keyword"]))
            
            items = universal_fetcher(source["id"], target_url)
            for item in items: item['interest_id'] = interest["id"]
            all_raw_data.extend(items)

    print(f"🚀 抓取完毕，共 {len(all_raw_data)} 条，开始 AI 处理...\n")

    for item in all_raw_data:
        print(f"🎯 正在处理: {item['title'][:30]}...")
        ai_data = analyze_with_gemma(item['title'], item['content'], item['source'])
        
        if ai_data:
            print(f"✅ 评分: {ai_data['importance_score']}")
            payload = {
                "title": item["title"],
                "summary": ai_data["summary"],
                "url": item["url"],
                "source_type": item["source"],
                "tags": ai_data["tags"],
                "importance_score": ai_data["importance_score"],
                "tech_difficulty": ai_data["tech_difficulty"],
                "social_value": ai_data["social_value"],
                "interest_id": item["interest_id"]
            }
            requests.post(CF_WORKER_URL, json=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}"}, timeout=10)
        
        time.sleep(2) # 稍微留点空隙给 Gemma 喘气

if __name__ == "__main__":
    main()