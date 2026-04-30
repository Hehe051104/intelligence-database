import os
import json
import time
import requests
import feedparser
from urllib.parse import quote
from openai import OpenAI

# ================= 配置与环境变量 =================
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY")
CF_WORKER_URL = os.environ.get("CF_WORKER_URL")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "SPEC-2026-SuperSecretKey")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 🚀 初始化智谱 OpenAI 兼容客户端
if ZHIPU_API_KEY:
    client = OpenAI(
        api_key=ZHIPU_API_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4"
    )

# ================= 核心功能引擎 =================
def load_config():
    """读取 JSON 配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def universal_fetcher(source_name, target_url):
    """RSS 情报抓取"""
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

def analyze_with_glm(title, content, source):
    """极简洗稿引擎：精准调用 GLM-4.7-Flash（附带自动重试装甲）"""
    if not ZHIPU_API_KEY: return None

    prompt = f"""
    来源：{source} | 标题：{title}
    正文：{content[:1500]}
    
    请严格提取以上信息并输出纯 JSON 字符串。不可包含 Markdown 代码块标记。
    结构：
    {{
        "summary": "50字内中文核心摘要",
        "tags": "3个英文标签,逗号分隔",
        "importance_score": 1-10整数,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话描述价值"
    }}
    """

    max_retries = 3  # 最大重试次数
    retry_delay = 5  # 初始等待秒数

    for attempt in range(max_retries):
        try:
            # 🎯 严格使用 glm-4.7-flash 模型
            res = client.chat.completions.create(
                model="glm-4.7-flash", 
                messages=[
                    {"role": "system", "content": "你是一个只输出 JSON 的情报分析机器。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1, 
                timeout=30 
            )

            raw_text = res.choices[0].message.content.strip()
            # 兼容处理可能出现的 Markdown 标签
            cleaned_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned_text)

        except Exception as e:
            error_msg = str(e)
            # 精准狙击智谱的限流和拥挤报错
            if "429" in error_msg or "1302" in error_msg or "1305" in error_msg:
                wait_time = retry_delay * (2 ** attempt) # 指数退避：5秒 -> 10秒 -> 20秒
                print(f"  └─ ⏳ [流量控制] 触发限流防御，{wait_time}秒后进行第 {attempt+1} 次重试...")
                import time # 确保引入time模块
                time.sleep(wait_time)
            else:
                # 如果是其他代码错误，直接抛弃不重试
                print(f"  └─ ⚠️ [处理异常] {e}")
                return None
                
    print("  └─ ❌ [彻底死心] 连续 3 次被服务器踢出，战术放弃该情报。")
    return None

# ================= 主控制流 =================
def main():
    config = load_config()
    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，开始执行 [数据源] x [兴趣点] 交叉扫描...\n")

    for source in config.get("sources", []):
        print(f"\n▶ 正在接入数据源: {source['name']}")
        for interest in config.get("interests", []):
            interest_id = interest["id"]
            if interest_id == "trending":
                target_url = source["trending_url"]
            else:
                target_url = source["search_url"].replace("{keyword}", quote(interest["keyword"]))
            
            fetched_items = universal_fetcher(source["id"], target_url)
            for item in fetched_items: item['interest_id'] = interest_id
            all_raw_data.extend(fetched_items)
            time.sleep(1) 

    print(f"\n⚡ 舰队集结完毕，共抓获 {len(all_raw_data)} 条原始情报。\n")

    for item in all_raw_data:
        print(f"🎯 [锁定] [{item['source']}] {item['title'][:40]}...")
        ai_data = analyze_with_glm(item['title'], item['content'], item['source'])
        
        if not ai_data or ai_data.get("importance_score", 0) < 5:
            print(f"🗑️ [抛弃] 价值过低。\n")
            continue
            
        print(f"✅ [提纯] 评分: {ai_data['importance_score']}")
        
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
            requests.post(CF_WORKER_URL, json=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}"}, timeout=10)
            print(f"🚀 [入库成功]！")
        except Exception as e:
            print(f"⚠️ [入库异常]: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()