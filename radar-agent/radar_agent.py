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

def analyze_with_gemini(title, content, source, interest_context=None, max_retries=3):
    """
    终极架构：精准对接 gemini-3.1-flash-lite-preview
    作为语义守门员，过滤无关、灌水内容，输出极专业标签
    """
    if not GEMINI_API_KEY:
        print("🚨 错误：未检测到 GEMINI_API_KEY")
        return None

    client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    # 构建领域上下文
    domain_context = f" | 所属领域: {interest_context['display_name']}"
    if interest_context.get('keyword'):
        domain_context += f" | 核心关键词: {interest_context['keyword']}"

    prompt = f"""
    你是 SPEC-2026 矩阵的**语义守门员**，职责是识别高价值情报并过滤日常灌水内容。

    领域上下文：{domain_context}
    来源：{source} | 标题：{title}
    正文：{content[:1500]}

    === 严格行为准则 ===
    1. **语义守门原则**：若内容是日常吐槽、无关信息、营销广告或重复新闻，强制将 importance_score 设为 0
    2. **专业度要求**：标签必须是高度垂直的技术/领域术语，拒绝通用模糊标签
    3. **价值判断**：importance_score 1-10，仅对具备情报价值的内容打分

    === 输出 JSON 格式 ===
    {{
        "summary": "50字内中文摘要",
        "tags": "3个极其专业的英文标签（使用斜杠分隔）",
        "importance_score": 0-10整数（无关内容必须为0）,
        "tech_difficulty": "Hard/Medium/Easy",
        "social_value": "一句话描述对该领域的价值"
    }}
    """

    # 重试循环
    for attempt in range(max_retries):
        try:
            res = client.chat.completions.create(
                model="gemini-3.1-flash-lite-preview",
                messages=[
                    {"role": "system", "content": "你是 SPEC-2026 的专业情报分析系统，严格输出 JSON 格式，绝不包含 Markdown 代码块。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                timeout=30
            )

            raw_text = res.choices[0].message.content.strip()
            cleaned_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)

        except json.JSONDecodeError as e:
            print(f"  └─ ⚠️ [格式错误] 模型输出非标准 JSON: {e}")
            return None
        except Exception as e:
            error_str = str(e)
            # 检查是否为 429 限流错误（Gemini 免费版限制 15 RPM）
            if "429" in error_str:
                print(f"  └─ ⚠️ [触发限流] 第 {attempt + 1}/{max_retries} 次重试，等待 60 秒...")
                time.sleep(60)
            elif "503" in error_str or "timed out" in error_str.lower():
                # 指数退避等待（非限流错误）
                wait_time = 2 ** attempt
                print(f"  └─ ⚠️ [暂时不可用] 第 {attempt + 1}/{max_retries} 次重试，等待 {wait_time} 秒...")
                time.sleep(wait_time)
            else:
                # 其他致命错误，直接返回
                print(f"  └─ ❌ [致命错误] {e}")
                return None

    # 循环结束仍未成功
    print(f"  └─ ❌ [重试耗尽] 已重试 {max_retries} 次均失败")
    return None

# ================= 主控制流 =================
def main():
    config = load_config()
    if not config: return

    all_raw_data = []
    print("\n⚡ 矩阵引擎启动，正在切入 Gemini 3.1 Flash Lite 轨道...\n")

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

    # 构建兴趣点 ID 到配置的映射，避免作用域污染
    interest_map = {interest["id"]: interest for interest in config.get("interests", [])}

    for item in all_raw_data:
        print(f"🎯 处理: {item['title'][:40]}...")

        # 通过 interest_id 反查配置上下文
        interest_id = item.get('interest_id', 'trending')
        interest_config = interest_map.get(interest_id, {'display_name': 'Unknown', 'keyword': ''})

        ai_data = analyze_with_gemini(
            item['title'],
            item['content'],
            item['source'],
            interest_context=interest_config
        )

        # 🛡️ 关键节流阀：强制冷却 4 秒（无论分析结果如何），适配 15 RPM 限额
        print("⏳ 全局节流阀 4 秒...")
        time.sleep(4)

        if ai_data is None:
            print(f"🗑️ [抛弃] 分析失败")
            continue

        importance_score = int(ai_data.get("importance_score", 0))

        if importance_score < 5:
            print(f"🗑️ [抛弃] 价值不足 (分数: {importance_score})")
            continue

        print(f"✅ 评分: {importance_score} | 正在跨海入库...")

        # 🛡️ 强制数据净化：绝不相信大模型的节操
        safe_tags = ai_data.get("tags", "")
        if isinstance(safe_tags, list):
            safe_tags = ", ".join([str(t) for t in safe_tags]) # 强行把数组拍扁成字符串

        safe_score = 5
        try:
            safe_score = int(ai_data.get("importance_score", 5)) # 强行转整数
        except:
            pass

        payload = {
            "title": str(item.get("title", "")),
            "summary": str(ai_data.get("summary", "")),
            "url": str(item.get("url", "")),
            "source_type": str(item.get("source", "")),
            "tags": str(safe_tags),
            "importance_score": safe_score,
            "tech_difficulty": str(ai_data.get("tech_difficulty", "Medium")),
            "social_value": str(ai_data.get("social_value", "")),
            "interest_id": str(item.get("interest_id", ""))
        }

        try:
            res = requests.post(CF_WORKER_URL, json=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}"}, timeout=10)
            if res.status_code == 200:
                print(f"🚀 [入库成功]！")
            else:
                print(f"⚠️ [入库失败] 状态码: {res.status_code} | {res.text[:100]}")
        except Exception as e:
            print(f"⚠️ [网络异常] 无法连接 Worker: {e}")

        print("⏳ 冷却管线 1.5 秒...\n")
        time.sleep(1.5)

if __name__ == "__main__":
    main()