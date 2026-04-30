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

def fetch_arxiv(query="cat:cs.AI", max_results=2):
    """学术触角：抓取最新论文"""
    print(f"📡 [arXiv] 扫描 {query} 最新论文...")
    url = f"http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        entries = feedparser.parse(response.content).entries
        # 标准化数据格式
        return [{"title": e.title, "content": e.summary, "url": e.link, "source": "arXiv"} for e in entries]
    except Exception as e:
        print(f"❌ [arXiv 阻断] {e}")
        return []

def fetch_reddit(subreddit="MachineLearning", max_results=2):
    """舆情触角：抓取 Reddit 每日最热"""
    print(f"📡 [Reddit] 渗透 r/{subreddit} 每日热榜...")
    url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t=day&limit={max_results}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        entries = feedparser.parse(response.content).entries
        return [{"title": e.title, "content": e.summary, "url": e.link, "source": "Reddit"} for e in entries]
    except Exception as e:
        print(f"❌ [Reddit 阻断] {e}")
        return []

def fetch_github(query="autonomous driving OR ROS language:python", max_results=2):
    """开源触角：抓取 GitHub 高星代码库"""
    print(f"📡 [GitHub] 搜刮 '{query}' 相关的热门项目...")
    # 查找过去7天内创建或更新的高星项目
    last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    url = f"https://api.github.com/search/repositories?q={query} pushed:>{last_week}&sort=stars&order=desc&per_page={max_results}"
    
    headers = HEADERS.copy()
    headers["Accept"] = "application/vnd.github.v3+json"
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        items = response.json().get("items", [])
        return [{
            "title": i["full_name"], 
            "content": f"{i['description']} | 语言: {i['language']} | Stars: {i['stargazers_count']}", 
            "url": i["html_url"], 
            "source": "GitHub"
        } for i in items]
    except Exception as e:
        print(f"❌ [GitHub 阻断] {e}")
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
    # 1. 组建混合舰队：同时出击三大数据源
    all_raw_data = []
    all_raw_data.extend(fetch_arxiv(query="cat:cs.AI", max_results=1))
    all_raw_data.extend(fetch_reddit(subreddit="MachineLearning", max_results=1))
    all_raw_data.extend(fetch_github(query="autonomous driving OR brain computer interface", max_results=1))
    
    print(f"\n⚡ 舰队集结完毕，共抓获 {len(all_raw_data)} 条原始情报，开始清洗...\n")

    # 2. 流水线作业
    for item in all_raw_data:
        print(f"🎯 [锁定] [{item['source']}] {item['title']}")
        
        ai_data = analyze_with_gemini(item['title'], item['content'], item['source'])
        
        if not ai_data or ai_data.get("importance_score", 0) < 5:
            print(f"🗑️ [抛弃] 价值过低，已过滤。")
            time.sleep(2) # 防并发限流
            continue
            
        print(f"✅ [提纯] 评分: {ai_data['importance_score']} | 标签: {ai_data['tags']}")
        
        payload = {
            "title": item["title"],
            "summary": ai_data["summary"],
            "url": item["url"],
            "source_type": item["source"], # 极其关键：前端筛选项的基石
            "tags": ai_data["tags"],
            "importance_score": ai_data["importance_score"],
            "tech_difficulty": ai_data["tech_difficulty"],
            "social_value": ai_data["social_value"]
        }
        
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}
        response = requests.post(CF_WORKER_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            print(f"🚀 [入库成功] {item['source']} 情报已发送！")
        else:
            print(f"⚠️ [入库失败] {response.text}")
            
        print("⏳ 冷却管线 5 秒...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()