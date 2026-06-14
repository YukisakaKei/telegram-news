import os
import sys
import json
import time
from datetime import datetime

# 强制 stdout/stderr 使用 UTF-8，避免 Windows 下中文乱码
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import feedparser
import requests


PROMPT_DEFAULTS = {
    "daily_news": (
        "你是一个专业的 AI 和科技领域新闻编辑。\n\n"
        "用户的兴趣领域：{interests}\n\n"
        "以下是今天抓取的新闻列表：\n\n"
        "{items}\n\n"
        "请完成以下任务：\n"
        "1. 从中筛选出与用户兴趣最相关、最重要的 10 条新闻\n"
        "2. 用中文为每条生成简洁摘要（1-2 句）\n"
        "3. 给出简短的影响分析\n"
        "4. 按重要性排序，用 ★ 评分（最高 ★★★★★，最低 ★★★☆☆）\n"
        "5. 每条新闻必须保留原始链接\n\n"
        "输出格式严格为（不要添加额外的前言后语）：\n\n"
        "【AI 日报】{date}\n\n"
        "★★★★★ **[标题](链接)**\n摘要：...\n影响：...\n\n"
        "★★★★☆ **[标题](链接)**\n摘要：...\n影响：..."
    ),
    "keyword_tracking_group": (
        "你是一个信息监控助手，帮助用户追踪特定主题的最新动态。\n\n"
        "追踪主题：{group}\n"
        "追踪关键词：{keywords}\n\n"
        "以下是今天从网络搜索（新闻、论坛、社交媒体）中抓取到的相关信息：\n"
        "{items}\n\n"
        "请完成以下任务：\n"
        "1. 筛选出最重要的 2-3 条信息\n"
        "2. 用中文为每条生成简洁摘要（1-2 句）\n"
        "3. 按重要性排序，用 ★ 评分\n"
        "4. 判断情感倾向（正面/负面/中性）\n"
        "5. ⚠️ 如果发现负面信息（投诉、维权、经营异常、资金链、跑路等），必须用 ⚠️ 特别标注并说明\n\n"
        "输出格式严格为（不要添加额外的前言后语）：\n\n"
        "## {group}\n\n"
        "★★★★★ **[标题](链接)**\n摘要：...\n来源：新闻/论坛/社交媒体\n情感：正面/负面/中性\n\n"
        "⚠️ 风险提示：（如有）"
    ),
    "keyword_tracking_flat": (
        "你是一个信息监控助手，帮助用户追踪特定关键词的最新动态。\n\n"
        "追踪关键词：{keywords}\n\n"
        "以下是今天从网络搜索（新闻、论坛、社交媒体）中抓取到的相关信息：\n\n"
        "{items}\n\n"
        "请完成以下任务：\n"
        "1. 筛选出最重要的 5-8 条信息\n"
        "2. 用中文为每条生成简洁摘要（1-2 句）\n"
        "3. 按重要性排序，用 ★ 评分\n"
        "4. 判断情感倾向（正面/负面/中性）\n"
        "5. ⚠️ 如果发现负面信息（投诉、维权、经营异常、资金链、跑路等），必须用 ⚠️ 特别标注并说明\n"
        "6. 最后给出综合风险评估（低/中/高）\n\n"
        "输出格式严格为（不要添加额外的前言后语）：\n\n"
        "🔍 关键词追踪 {date}\n\n"
        "追踪：{keywords}\n\n"
        "★★★★★ **[标题](链接)**\n摘要：...\n来源：新闻/论坛/社交媒体\n情感：正面/负面/中性\n\n"
        "⚠️ 风险提示：（如有）\n\n综合风险评估：低/中/高"
    ),
    "risk_assessment": (
        "以下是根据各主题追踪结果，请给出一个综合风险评估（低/中/高），用一句话说明理由。\n\n"
        "追踪结果摘要：\n{groups_summary}\n\n"
        "输出格式严格为（不要添加额外的前言后语）：\n综合风险评估：低/中/高\n说明：..."
    ),
}


def _load_prompts():
    try:
        with open("prompts.json", encoding="utf-8") as f:
            loaded = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        loaded = {}
    prompts = dict(PROMPT_DEFAULTS)
    prompts.update(loaded)
    return prompts


def _build_prompt(key, **kwargs):
    template = PROMPTS.get(key, PROMPT_DEFAULTS.get(key, ""))
    return template.format(**kwargs)


PROMPTS = _load_prompts()


def _parse_list(env_val):
    return [x.strip() for x in env_val.split(",") if x.strip()]


def _parse_groups(env_val):
    if not env_val:
        return {}
    groups = {}
    for part in env_val.split(";"):
        part = part.strip()
        if ":" not in part:
            continue
        name, kw_str = part.split(":", 1)
        name = name.strip()
        keywords = [k.strip() for k in kw_str.split(",") if k.strip()]
        if name and keywords:
            groups[name] = keywords
    return groups


RSS_FEEDS = _parse_list(os.getenv("RSS_FEEDS", ""))
INTERESTS = _parse_list(os.getenv("INTERESTS", ""))
SEARCH_KEYWORDS = _parse_list(os.getenv("SEARCH_KEYWORDS", ""))
SEARCH_KEYWORD_GROUPS = _parse_groups(os.getenv("SEARCH_KEYWORD_GROUPS", ""))
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
SEARCH_TIME_RANGE = os.getenv("SEARCH_TIME_RANGE", "m")
TEST_MODE = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

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


def _search_google_news(keyword, items, group=None):
    import urllib.parse
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    feed = feedparser.parse(url)
    for entry in feed.entries[:5]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))[:300]
        item = {
            "title": title, "link": link, "summary": summary,
            "published": entry.get("published", ""),
            "source": "news", "keyword": keyword,
        }
        if group:
            item["group"] = group
        items.append(item)
    print(f"[INFO] Google News: {len(feed.entries[:5])} results for '{keyword}'")


def _search_bing_web(keyword, max_results, items, group=None):
    import urllib.parse
    import re

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    url = f"https://www.bing.com/search?q={urllib.parse.quote(keyword)}&setlang=zh-cn&count={max_results}&tbs=qdr:{SEARCH_TIME_RANGE}"
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        print(f"[WARN] Bing search returned {resp.status_code}")
        return

    blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', resp.text, re.DOTALL)
    for block in blocks[:max_results]:
        link_m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link_m:
            continue
        href = link_m.group(1)
        title = _strip_html(link_m.group(2)).strip()
        snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = _strip_html(snippet_m.group(1)).strip()[:300] if snippet_m else ""
        item = {
            "title": title, "link": href, "summary": snippet,
            "published": "", "source": "web", "keyword": keyword,
        }
        if group:
            item["group"] = group
        items.append(item)
    print(f"[INFO] Bing web: {len(blocks[:max_results])} results for '{keyword}'")


def search_keywords():
    if SEARCH_KEYWORD_GROUPS:
        groups = SEARCH_KEYWORD_GROUPS
        keywords = []
        for kw_list in groups.values():
            keywords.extend(kw_list)
    else:
        groups = None
        keywords = SEARCH_KEYWORDS

    if not keywords:
        return [], groups

    max_results = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
    items = []

    for keyword in keywords:
        group = None
        if groups:
            for gname, kws in groups.items():
                if keyword in kws:
                    group = gname
                    break
        try:
            _search_google_news(keyword, items, group)
        except Exception as e:
            print(f"[WARN] Google News search failed for '{keyword}': {e}")
        try:
            _search_bing_web(keyword, max_results, items, group)
        except Exception as e:
            print(f"[WARN] Bing web search failed for '{keyword}': {e}")

    print(f"[INFO] Search returned {len(items)} results for {len(keywords)} keyword(s)")
    return items, groups


def summarize_with_deepseek(news_items):
    if not news_items:
        return None

    news_text = ""
    for i, item in enumerate(news_items):
        news_text += f"{i + 1}. [{item['title']}]({item['link']})\n"
        if item["summary"]:
            news_text += f"   摘要: {item['summary'][:200]}\n"

    now = datetime.now()
    prompt = _build_prompt("daily_news",
        interests=", ".join(INTERESTS),
        date=now.strftime('%Y年%m月%d日'),
        items=news_text,
    )
    return _call_deepseek(prompt)


def _call_deepseek(prompt):
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
    return data["choices"][0]["message"]["content"]


def summarize_keyword_tracking(tracking_items, groups=None):
    if not tracking_items:
        return None

    now = datetime.now()

    if groups:
        parts = [f"🔍 关键词追踪 {now.strftime('%Y年%m月%d日')}"]
        for gname, kws in groups.items():
            group_items = [it for it in tracking_items if it.get("group") == gname]
            if not group_items:
                parts.append(f"\n## {gname}\n(无相关结果)")
                continue

            items_text = ""
            for i, item in enumerate(group_items):
                src = item.get("source", "web")
                items_text += f"{i + 1}. [{item['title']}]({item['link']}) [{src}]\n"
                if item["summary"]:
                    items_text += f"   摘要: {item['summary'][:200]}\n"

            prompt = _build_prompt(f"group_{gname}" if f"group_{gname}" in PROMPTS else "keyword_tracking_group",
                group=gname,
                keywords=", ".join(kws),
                items=items_text,
            )
            print(f"[INFO] Calling DeepSeek for group '{gname}' ({len(group_items)} items)")
            result = _call_deepseek(prompt)
            if result:
                parts.append(result.strip())
            else:
                parts.append(f"\n## {gname}\n(摘要生成失败)")

        risk_prompt = _build_prompt("risk_assessment",
            groups_summary="\n".join(parts[-len(groups):]),
        )
        risk_result = _call_deepseek(risk_prompt)
        if risk_result:
            parts.append(risk_result.strip())

        return "\n".join(parts)

    else:
        keywords = SEARCH_KEYWORDS
        items_text = ""
        for i, item in enumerate(tracking_items):
            src = item.get("source", "web")
            items_text += f"{i + 1}. [{item['title']}]({item['link']}) [{src}]\n"
            if item["summary"]:
                items_text += f"   摘要: {item['summary'][:200]}\n"

        prompt = _build_prompt("keyword_tracking_flat",
            keywords=", ".join(keywords),
            date=now.strftime('%Y年%m月%d日'),
            items=items_text,
        )
        return _call_deepseek(prompt)


def send_telegram(text):
    if not text:
        return

    if TEST_MODE:
        _save_local_output(text)
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


def _save_local_output(text):
    os.makedirs("output", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"output/bot_{ts}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[TEST] Output saved to {path} ({len(text)} chars)")


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
    if not TEST_MODE:
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

    # AI 日报
    news_items = fetch_all_news()
    if news_items:
        report = summarize_with_deepseek(news_items)
        if not report:
            print("[WARN] AI summarization failed, sending raw news list")
            report = _build_fallback_report(news_items)
        send_telegram(report)
    else:
        send_telegram("⚠️ 今日新闻抓取失败，请检查 RSS 源。")

    # 关键词追踪
    has_keywords = bool(SEARCH_KEYWORDS) or bool(SEARCH_KEYWORD_GROUPS)
    if has_keywords:
        tracking_items, groups = search_keywords()
        if tracking_items:
            tracking_report = summarize_keyword_tracking(tracking_items, groups)
            if not tracking_report:
                print("[WARN] Tracking summarization failed, sending raw list")
                keywords = [kw for kws in (groups or {}).values() for kw in kws] or SEARCH_KEYWORDS
                tracking_report = _build_tracking_fallback(tracking_items, keywords)
            send_telegram(tracking_report)
        else:
            print("[INFO] No tracking results found for keywords")

    print(f"[DONE] AI News Bot finished - {datetime.now().isoformat()}")


def _build_fallback_report(items):
    now = datetime.now()
    lines = [f"【AI 日报】{now.strftime('%Y年%m月%d日')}", ""]
    lines.append("(AI 摘要生成失败，以下是原始新闻列表)", "")
    for i, item in enumerate(items[:15]):
        lines.append(f"{i + 1}. [{item['title']}]({item['link']})")
    return "\n".join(lines)


def _build_tracking_fallback(items, keywords):
    now = datetime.now()
    lines = [f"🔍 关键词追踪 {now.strftime('%Y年%m月%d日')}", ""]
    lines.append(f"追踪：{', '.join(keywords)}", "")
    lines.append("(AI 摘要生成失败，以下是原始搜索结果)", "")
    for i, item in enumerate(items[:15]):
        src = item.get("source", "web")
        lines.append(f"{i + 1}. [{item['title']}]({item['link']}) [{src}]")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
