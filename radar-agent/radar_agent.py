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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# ================= 核心功能引擎 =================
def load_config():
    """读取配置文件"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"🚨 配置文件读取失败: {e}")
        return None

def universal_fetcher(source_name, target_url):
    """RSS 抓取引擎"""
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

def analyze_with_gemini(title, content, source):
    """
    使用 Gemini 3.1 Flash Lite 进行情报提纯
    保持代码干爽，仅保留最基础的解析逻辑
    """
    if not GEMINI_API_KEY:
        return None

    # 🎯 严格锁定 Gemini 3.1 Flash Lite 模型
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    作为专业情报员，请将以下内容提取为纯 JSON。
    来源：{source} | 标题：{title}
    正文：{content[:1500]}

    严格输出以下 JSON 结构：
    {{
        "summary": "50字内中文摘要",
        "tags": "3个英文标签",
        "importance_score": 1-10整数,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话描述价值"
    }}
    """

    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, json=payload, timeout=30)
        
        if resp.status_code != 200:
            print(f"  └─ ❌ [API拒绝] 状态码: {resp.status_code}")
            return None

        result = resp.json()
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # 移除可能存在的 Markdown 包裹，保持干爽
        cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)

    except Exception as e:
        print(f"  └─ ⚠️ [提纯失败] {e}")
        return None

# ================= 主控制流 =================
def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，正在切换至 Gemini 3.1 Flash 轨道...\n")

    # 1. 采集
    for source in config.get("sources", []):
        print(f"▶ 数据源: {source['name']}")
        for interest in config.get("interests", []):
            target_url = source["trending_url"] if interest["id"] == "trending" else \
                         source["search_url"].replace("{keyword}", quote(interest["keyword"]))
            
            items = universal_fetcher(source["id"], target_url)
            for item in items: item['interest_id'] = interest["id"]
            all_raw_data.extend(items)
            time.sleep(1)

    print(f"\n⚡ 抓获 {len(all_raw_data)} 条情报，开始提纯...\n")

    # 2. 提纯入库
    for item in all_raw_data:
        print(f"🎯 处理: {item['title'][:40]}...")
        ai_data = analyze_with_gemini(item['title'], item['content'], item['source'])
        
        if ai_data and int(ai_data.get("importance_score", 0)) >= 5:
            print(f"✅ 评分: {ai_data['importance_score']} | 入库中...")
            payload = {**ai_data, "title": item["title"], "url": item["url"], 
                       "source_type": item["source"], "interest_id": item["interest_id"]}
            
            try:
                requests.post(CF_WORKER_URL, json=payload, 
                              headers={"Authorization": f"Bearer {AUTH_TOKEN}"}, timeout=10)
            except:
                pass
        else:
            print(f"🗑️ [抛弃] 价值不足或处理失败")
            
        time.sleep(1.2) # 500次/天，每秒跑一条绰绰有余

if __name__ == "__main__":
    main()