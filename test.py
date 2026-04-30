import os
from openai import OpenAI

# 利用 OpenAI 兼容层直捣黄龙
client = OpenAI(
    api_key='AIzaSyB8kwDW4XRI4nVGr8hsRg338BjxBbmHK6s' ,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

print("📡 正在潜入 Google API 档案库，拉取所有 Flash 轻量级模型...\n")

try:
    models = client.models.list()
    found = False
    for model in models:
        # 只过滤出带有 flash 或者 lite 或者 8b 字眼的高频模型
        if 'flash' in model.id.lower() or 'lite' in model.id.lower() or '8b' in model.id.lower():
            print(f"✅ 锁定真实可用代号: {model.id}")
            found = True
            
    if not found:
        print("❌ 警告：你的 API 密钥权限池中，未能检索到任何 Flash 系列模型！")
except Exception as e:
    print(f"🚨 探测失败: {e}")

# ✅ 锁定真实可用代号: models/gemini-2.5-flash
# ✅ 锁定真实可用代号: models/gemini-2.0-flash
# ✅ 锁定真实可用代号: models/gemini-2.0-flash-001
# ✅ 锁定真实可用代号: models/gemini-2.0-flash-lite-001
# ✅ 锁定真实可用代号: models/gemini-2.0-flash-lite
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-preview-tts
# ✅ 锁定真实可用代号: models/gemini-flash-latest
# ✅ 锁定真实可用代号: models/gemini-flash-lite-latest
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-lite
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-image
# ✅ 锁定真实可用代号: models/gemini-3-flash-preview
# ✅ 锁定真实可用代号: models/gemini-3.1-flash-lite-preview
# ✅ 锁定真实可用代号: models/gemini-3.1-flash-image-preview
# ✅ 锁定真实可用代号: models/gemini-3.1-flash-tts-preview
# ✅ 锁定真实可用代号: models/veo-3.1-lite-generate-preview
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-native-audio-latest
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-native-audio-preview-09-2025
# ✅ 锁定真实可用代号: models/gemini-2.5-flash-native-audio-preview-12-2025
# ✅ 锁定真实可用代号: models/gemini-3.1-flash-live-preview