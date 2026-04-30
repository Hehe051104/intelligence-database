import os
import json
import time
import requests
import feedparser
from urllib.parse import quote

# ================= 配置与环境变量 =================
# 确保你的 GitHub Secrets 变量名是 GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CF_WORKER_URL = os.environ.get("CF_WORKER_URL")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "SPEC-2026-SuperSecretKey")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# ================= 核心功能引擎 =================
def load_config():
    """读取同目录下的 config.json"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"🚨 配置文件读取失败: {e}")
        return None

def universal_fetcher(source_name, target_url):
    """通用的 RSS/Atom 抓取器"""
    try:
        print(f"  └─ 📡 扫描信号: {target_url[:60]}...")
        response = requests.get(target_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        return [{
            "title": e.title, 
            "content": getattr(e, 'summary', getattr(e, 'description', '')), 
            "url": getattr(e, 'link', ''), 
            "source": source_name
        } for e in feed.entries]
    except Exception as e:
        print(f"  └─ ❌ [抓取中断] {e}")
        return []

def analyze_with_gemma(title, content, source):
    """调用 Gemma 4 31B 进行提纯，自带防爆解析逻辑"""
    if not GEMINI_API_KEY:
        print("🚨 错误：未检测到 GEMINI_API_KEY")
        return None

    # 精准对接 Gemma 4 31B 官方 API 路径
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-4-31b-it:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    You are a professional tech analyst. Summarize the following content into a STRICT JSON format.
    Source: {source}
    Title: {title}
    Text: {content[:1500]}

    Output structure (MUST be valid JSON):
    {{
        "summary": "一段50字内的中文核心摘要",
        "tags": "3个英文核心标签",
        "importance_score": 1-10的整数,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话描述其潜在应用价值"
    }}
    """

    try:
        # 给 31B 模型足够的思考时间
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=payload, timeout=60)
        
        if resp.status_code != 200:
            print(f"  └─ ❌ [API拒绝] 状态码: {resp.status_code}")
            return None

        result = resp.json()
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # 修正：完整的清洗逻辑，防止 SyntaxError
        cleaned_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        
        return json.loads(cleaned_text)

    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"  └─ ⚠️ [提纯失败] {e}")
        return None

# ================= 主控制逻辑 =================
def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，开始执行情报扫描...\n")

    # 1. 数据采集阶段
    for source in config.get("sources", []):
        print(f"▶ 正在接入数据源: {source['name']}")
        
        for interest in config.get("interests", []):
            interest_id = interest["id"]
            if interest_id == "trending":
                target_url = source["trending_url"]
                print(f"  ├─ [任务] 探测全网热门")
            else:
                target_url = source["search_url"].replace("{keyword}", quote(interest["keyword"]))
                print(f"  ├─ [任务] 追踪: {interest['display_name']}")
            
            items = universal_fetcher(source["id"], target_url)
            for item in items:
                item['interest_id'] = interest_id
            all_raw_data.extend(items)
            time.sleep(1)

    print(f"\n⚡ 舰队集结完毕，共抓获 {len(all_raw_data)} 条原始情报，开始 AI 提纯...\n")

    # 2. AI 提纯与入库阶段
    for item in all_raw_data:
        print(f"🎯 正在处理: {item['title'][:40]}...")
        
        ai_data = analyze_with_gemma(item['title'], item['content'], item['source'])
        
        # 过滤掉低价值内容（评分低于 5 的不要）
        if not ai_data or int(ai_data.get("importance_score", 0)) < 5:
            print(f"🗑️ [抛弃] 噪音数据或价值过低。\n")
            continue
            
        print(f"✅ [提纯] 评分: {ai_data['importance_score']} | 标签: {ai_data['tags']}")
        
        # 构造入库 Payload
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
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Content-Type": "application/json"
        }
        
        try:
            res = requests.post(CF_WORKER_URL, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                print(f"🚀 [入库成功]！")
            else:
                print(f"⚠️ [入库失败] 状态码: {res.status_code}")
        except Exception as e:
            print(f"⚠️ [网络异常] 无法连接 Worker: {e}")
            
        print("⏳ 冷却管线 2 秒...\n")
        time.sleep(2)

if __name__ == "__main__":
    main()