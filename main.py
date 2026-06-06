import os
import json
import time
from datetime import datetime

import feedparser
import requests


RSS_FEEDS = _parse_list(os.getenv("RSS_FEEDS", ""))
INTERESTS = _parse_list(os.getenv("INTERESTS", ""))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")


def _parse_list(env_val):
    return [x.strip() for x in env_val.split(",") if x.strip()]

MAX_ITEMS_PER_FEED = 10
MAX_TOTAL_ITEMS = 60
TELEGRAM_MAX_LENGTH = 4000


def fetch_all_news():
    items = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                summary = ""
                if entry.get("summary"):
                    summary = entry.get("summary", "")
                elif entry.get("description"):
                    summary = entry.get("description", "")
                summary = _strip_html(summary)[:300]
                published = entry.get("published", "")
                items.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published,
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch {url}: {e}")

    items = items[:MAX_TOTAL_ITEMS]
    print(f"[INFO] Fetched {len(items)} news items from {len(RSS_FEEDS)} feeds")
    return items


def _strip_html(text):
    import re
    return re.sub(r"<[^>]+>", "", text)


def summarize_with_deepseek(news_items):
    if not news_items:
        return None

    news_text = ""
    for i, item in enumerate(news_items):
        news_text += f"{i + 1}. [{item['title']}]({item['link']})\n"
        if item["summary"]:
            news_text += f"   摘要: {item['summary'][:200]}\n"

    now = datetime.now()
    prompt = f"""你是一个专业的 AI 和科技领域新闻编辑。

用户的兴趣领域：{', '.join(INTERESTS)}

以下是今天抓取的新闻列表：

{news_text}

请完成以下任务：
1. 从中筛选出与用户兴趣最相关、最重要的 10 条新闻
2. 用中文为每条生成简洁摘要（1-2 句）
3. 给出简短的影响分析
4. 按重要性排序，用 ★ 评分（最高 ★★★★★，最低 ★★★☆☆）
5. 每条新闻必须保留原始链接

输出格式严格为（不要添加额外的前言后语）：

【AI 日报】{now.strftime('%Y年%m月%d日')}

★★★★★ **标题**
摘要：...
影响：...
🔗 链接

★★★★☆ **标题**
摘要：...
影响：...
🔗 链接
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 4000,
    }

    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"[ERROR] DeepSeek API error: {resp.status_code} {resp.text}")
        return None

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return content


def send_telegram(text):
    if not text:
        return

    chunks = _split_text(text, TELEGRAM_MAX_LENGTH)
    for chunk in chunks:
        resp = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            print(f"[INFO] Telegram message sent ({len(chunk)} chars)")
        else:
            print(f"[ERROR] Telegram API error: {resp.status_code} {resp.text}")
            _send_fallback(chunk)


def _send_fallback(text):
    """Send without Markdown parse mode if Markdown fails"""
    resp = requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    if resp.status_code == 200:
        print("[INFO] Telegram message sent (fallback, plain text)")
    else:
        print(f"[ERROR] Telegram fallback also failed: {resp.status_code} {resp.text}")


def _split_text(text, max_len):
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def validate_config():
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not TG_BOT_TOKEN:
        missing.append("TG_BOT_TOKEN")
    if not TG_CHAT_ID:
        missing.append("TG_CHAT_ID")
    if not RSS_FEEDS:
        missing.append("RSS_FEEDS")
    if not INTERESTS:
        missing.append("INTERESTS")
    if missing:
        print(f"[FATAL] Missing environment variables: {', '.join(missing)}")
        return False
    return True


def main():
    print(f"[START] AI News Bot - {datetime.now().isoformat()}")

    if not validate_config():
        return

    news_items = fetch_all_news()
    if not news_items:
        print("[WARN] No news fetched, sending error notification")
        send_telegram("⚠️ 今日新闻抓取失败，请检查 RSS 源。")
        return

    report = summarize_with_deepseek(news_items)
    if not report:
        print("[WARN] Summarization failed, sending raw news list as fallback")
        report = _build_fallback_report(news_items)

    send_telegram(report)
    print(f"[DONE] AI News Bot finished - {datetime.now().isoformat()}")


def _build_fallback_report(items):
    now = datetime.now()
    lines = [f"【AI 日报】{now.strftime('%Y年%m月%d日')}", ""]
    lines.append("(AI 摘要生成失败，以下是原始新闻列表)", "")
    for i, item in enumerate(items[:15]):
        lines.append(f"{i + 1}. [{item['title']}]({item['link']})")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
