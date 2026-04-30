import os
import feedparser
import requests
import time
import json
from openai import OpenAI
from datetime import datetime, timedelta

# ==========================================
# 核心配置区：特工 V2.0 终极装备库
# ==========================================
# 以下参数都删去，防止上传到公共。具体在github上部署时，用环境变量解决
CF_WORKER_URL = os.environ.get("CF_WORKER_URL")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "") # 这个可以是空的

if not all([CF_WORKER_URL, AUTH_TOKEN, GEMINI_API_KEY]):
    raise ValueError("🚨 [致命错误] 缺少必要的环境变量密钥！")

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 终极伪装面具：应对所有反爬机制
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# 情报源获取模块 (多维触角)
# ==========================================

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def universal_fetcher(source_name, target_url):
    """终极情报抓取器：只认标准 RSS/Atom 协议，不问出处"""
    print(f"  └─ 📡 扫描信号: {target_url[:60]}...")
    try:
        response = requests.get(target_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        entries = feedparser.parse(response.content).entries
        
        # 统一格式化输出
        return [{
            "title": e.title, 
            "content": getattr(e, 'summary', getattr(e, 'description', '')), 
            "url": getattr(e, 'link', ''), 
            "source": source_name
        } for e in entries]
    except Exception as e:
        print(f"  └─ ❌ [节点阻断] {e}")
        return []

# ==========================================
# 提纯与发射模块
# ==========================================

def analyze_with_gemini(title, content, source_type):
    """动态提纯：针对不同来源采取不同的审问策略"""
    prompt = f"""
    你是一个极其严苛的技术情报分析师。当前处理的情报来源于：【{source_type}】。
    请根据来源特性，提取关键信息，严格以 JSON 格式输出：
    - summary: 中文总结（一针见血，不超过150字。如果是论文，提炼核心创新；如果是代码，提炼其功能；如果是论坛帖子，提炼核心争议或发现）。
    - tags: 英文标签字符串（如 "Autonomous_Driving, LLM, ROS"，逗号分隔）。
    - importance_score: 1-10的整数评分（极其严苛！只有极其颠覆性、或者极其有用的开源代码才能给8分以上。普通的灌水、求助贴给3分以下）。
    - tech_difficulty: 字符串（"Easy", "Medium", "Hard"）。
    - social_value: 中文简述（该情报的实际落地价值）。
    """
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"标题: {title}\n内容: {content}"}
            ],
            response_format={"type": "json_object"},
            timeout=15
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ [大模型崩溃] {e}")
        return None

def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    
    print("\n⚡ 矩阵引擎启动，开始执行 [数据源] x [兴趣点] 交叉扫描...\n")

    # 核心：双层循环的笛卡尔积检索
    for source in config.get("sources", []):
        print(f"▶ 正在接入数据源: {source['name']}")
        
        for interest in config.get("interests", []):
            interest_id = interest["id"]
            keyword = interest["keyword"]
            
            # 逻辑分流：是抓全网热门，还是抓特定关键词？
            if interest_id == "trending":
                target_url = source["trending_url"]
                print(f"  ├─ [任务] 探测默认全网热门")
            else:
                # 把关键词进行 URL 编码后填入模板
                encoded_keyword = quote(keyword)
                target_url = source["search_url"].replace("{keyword}", encoded_keyword)
                print(f"  ├─ [任务] 追踪兴趣点: {interest['display_name']}")
            
            # 丢给万能抓取器
            fetched_items = universal_fetcher(source["id"], target_url)
            
            # 极其重要：在原始数据中打上“兴趣标签”，方便前端过滤
            for item in fetched_items:
                item['interest_id'] = interest_id
            
            all_raw_data.extend(fetched_items)
            time.sleep(1) # 避免触发反爬

    print(f"\n⚡ 舰队集结完毕，共抓获 {len(all_raw_data)} 条原始情报，准备提纯入库...\n")

if __name__ == "__main__":
    main()
