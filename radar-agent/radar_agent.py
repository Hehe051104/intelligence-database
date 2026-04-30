import os
import json
import time
import requests
import feedparser
from urllib.parse import quote
from openai import OpenAI

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
    终极架构：通过 OpenAI SDK 兼容层精准调用 gemini-3.1-flash-lite
    代码极度干爽，将网络底层逻辑全盘交给官方 SDK
    """
    if not GEMINI_API_KEY:
        print("🚨 错误：未检测到 GEMINI_API_KEY")
        return None

    # 初始化 OpenAI 客户端，但把枪口对准 Google 的服务器
    client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

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
        # 🎯 完美调用你指定的 3.1 Lite 模型
        res = client.chat.completions.create(
            model="gemini-3.1-flash-lite-preview",
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 格式的情报分析机器。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            timeout=30
        )

        raw_text = res.choices[0].message.content.strip()
        
        # 极简清洗：去掉可能带有的 Markdown 代码块标记
        cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_text)

    except json.JSONDecodeError as e:
        print(f"  └─ ⚠️ [格式错误] 模型输出非标准 JSON: {e}")
        return None
    except Exception as e:
        print(f"  └─ ❌ [API调用失败] {e}")
        return None

# ================= 主控制流 =================
def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，正在切入 Gemini 3.1 Flash Lite 轨道...\n")

    # 1. 采集数据
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
        
        # 分数阈值卡在 5 分，及格线以上才入库
        if ai_data and int(ai_data.get("importance_score", 0)) >= 5:
            print(f"✅ 评分: {ai_data['importance_score']} | 正在跨海入库...")
            
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
            
            try:
                res = requests.post(CF_WORKER_URL, json=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}"}, timeout=10)
                if res.status_code == 200:
                    print(f"🚀 [入库成功]！")
                else:
                    print(f"⚠️ [入库失败] 状态码: {res.status_code}")
            except Exception as e:
                print(f"⚠️ [网络异常] 无法连接 Worker: {e}")
        else:
            print(f"🗑️ [抛弃] 价值不足或处理失败")
            
        print("⏳ 冷却管线 1.5 秒...\n")
        time.sleep(1.5) # 完美适配每天 500 次的限流节奏

if __name__ == "__main__":
    main()