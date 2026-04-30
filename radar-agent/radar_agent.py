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
    """读取 JSON 配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def universal_fetcher(source_name, target_url):
    """终极情报抓取器：只认标准 RSS/Atom 协议"""
    print(f"  └─ 📡 扫描信号: {target_url[:70]}...")
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
        print(f"  └─ ❌ [节点阻断] {e}")
        return []

def analyze_with_gemini(title, content, source):
    """调用 Gemini 2.5 进行数据清洗与高维特征提取"""
    if not GEMINI_API_KEY:
        print("🚨 未检测到 GEMINI_API_KEY 环境变量！")
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    作为顶尖科技情报分析师，请精简以下内容。
    来源：{source}
    标题：{title}
    正文片段：{content[:1500]}
    
    请严格返回以下JSON格式（不要包含任何Markdown代码块标记）：
    {{
        "summary": "用中文写一段50字左右的核心摘要，一针见血。",
        "tags": "3个英文核心标签，逗号分隔",
        "importance_score": 1到10的整数评估其技术含金量,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话中文描述其潜在的应用场景或商业落地价值"
    }}
    """
    
    try:
        resp = requests.post(
            url, 
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        )
        resp_json = resp.json()
        
        # 提取 Gemini 返回的文本并清理可能的 markdown 标记
        raw_text = resp_json['candidates'][0]['content']['parts'][0]['text']
        cleaned_text = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
        
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"  └─ ⚠️ [AI 处理异常] {e}")
        return None

# ================= 主控制流 =================
def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，开始执行 [数据源] x [兴趣点] 交叉扫描...\n")

    # 1. 笛卡尔积交叉抓取
    for source in config.get("sources", []):
        print(f"\n▶ 正在接入数据源: {source['name']}")
        
        for interest in config.get("interests", []):
            interest_id = interest["id"]
            keyword = interest["keyword"]
            
            if interest_id == "trending":
                target_url = source["trending_url"]
                print(f"  ├─ [任务] 探测默认全网热门")
            else:
                target_url = source["search_url"].replace("{keyword}", quote(keyword))
                print(f"  ├─ [任务] 追踪兴趣点: {interest['display_name']}")
            
            fetched_items = universal_fetcher(source["id"], target_url)
            
            # 打上双维度标签
            for item in fetched_items:
                item['interest_id'] = interest_id
            
            all_raw_data.extend(fetched_items)
            time.sleep(1.5) 

    print(f"\n⚡ 舰队集结完毕，共抓获 {len(all_raw_data)} 条原始情报，准备提纯入库...\n")

    # 2. AI 提纯与跨海入库
    for item in all_raw_data:
        print(f"🎯 [锁定] [{item['source']}] {item['title'][:40]}...")
        
        ai_data = analyze_with_gemini(item['title'], item['content'], item['source'])
        
        if not ai_data or ai_data.get("importance_score", 0) < 5:
            print(f"🗑️ [抛弃] 噪音数据或价值过低。\n")
            time.sleep(2) 
            continue
            
        print(f"✅ [提纯] 评分: {ai_data['importance_score']} | 标签: {ai_data['tags']}")
        
        payload = {
            "title": item["title"],
            "summary": ai_data["summary"],
            "url": item["url"],
            "source_type": item["source"],
            "tags": ai_data["tags"],
            "importance_score": ai_data["importance_score"],
            "tech_difficulty": ai_data["tech_difficulty"],
            "social_value": ai_data["social_value"],
            "interest_id": item["interest_id"] # 极其关键的跨维字段
        }
        
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}", 
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(CF_WORKER_URL, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"🚀 [入库成功] 情报已写入 D1 与 Vectorize 矩阵！")
            else:
                print(f"⚠️ [入库失败] 状态码: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"⚠️ [网络异常] 无法连接网关: {e}")
            
        print("⏳ 冷却管线 4 秒...\n")
        time.sleep(4)

if __name__ == "__main__":
    main()