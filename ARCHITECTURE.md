# 项目逻辑说明

## 概述

定时抓取 RSS + 网页搜索 → DeepSeek AI 筛选摘要 → 推送到 Telegram 频道。分为两大模块：**AI 日报**（RSS 新闻推荐）和**关键词追踪**（舆情/动态监控）。

## 执行流程

```
main()
├── validate_config()        # 校验环境变量完整性
├── [AI 日报]
│   ├── fetch_all_news()     # 遍历 RSS_FEEDS，每个源取最多 10 条
│   ├── summarize_with_deepseek()  # 调用 DeepSeek 筛选 10 条、生成中文摘要 + 影响分析 + ★ 评分
│   └── send_telegram()      # 按 Markdown 格式发送，超 4000 字自动分段
└── [关键词追踪]
    ├── search_keywords()    # 每个关键词分别搜索 Google News RSS + Bing 网页
    ├── summarize_keyword_tracking()  # DeepSeek 筛选 5-8 条、情感判定、风险标注
    └── send_telegram()
```

## 模块详解

### 1. 配置加载 (`main.py:1-27`)

- 通过 `python-dotenv` 从 `.env` 加载环境变量
- `_parse_list()` 将逗号分隔字符串转为列表
- 必需项：`DEEPSEEK_API_KEY`、`TG_BOT_TOKEN`、`TG_CHAT_ID`、`RSS_FEEDS`、`INTERESTS`
- 可选项：`SEARCH_KEYWORDS`（为空则跳过关键词追踪）、`HTTPS_PROXY`

### 2. AI 日报 (`main.py:31-173`)

**fetch_all_news()** — RSS 抓取
- 使用 `feedparser` 解析每个 RSS 源
- 每源最多取 10 条（`MAX_ITEMS_PER_FEED`），总计不超过 60 条（`MAX_TOTAL_ITEMS`）
- 字段：title、link、summary（去 HTML 标签，截取前 300 字）、published

**summarize_with_deepseek()** — AI 摘要
- 将所有新闻拼接为编号列表，附带用户兴趣关键词
- Prompt 要求：筛选 10 条最相关新闻 → 中文摘要 → 影响分析 → ★ 评分排序
- 模型 `deepseek-chat`，temperature=0.3，max_tokens=4000
- 失败时降级为原始列表 (`_build_fallback_report`)

### 3. 关键词追踪 (`main.py:65-246`)

**search_keywords()** — 双引擎搜索
- **Google News RSS**：`https://news.google.com/rss/search?q=<keyword>&hl=zh-CN`
- **Bing 网页搜索**：直连 `www.bing.com`，正则解析 `<li class="b_algo">` 块提取标题/链接/摘要
- 每条结果标注来源 `news` 或 `web`

**summarize_keyword_tracking()** — 舆情分析
- Prompt 要求：筛选 5-8 条 → 中文摘要 → 情感判定（正面/负面/中性）
- 特殊逻辑：检测投诉、维权、经营异常等负面信息，用 ⚠️ 标注
- 最后输出综合风险评估（低/中/高）

### 4. Telegram 推送 (`main.py:249-301`)

- 使用 Bot API `sendMessage`，`parse_mode: "Markdown"`
- 超 4000 字符自动按行拆分为多条消息 (`_split_text`)
- Markdown 解析失败时自动降级为纯文本发送 (`_send_fallback`)

## 运行方式

### 本地

```bash
pip install -r requirements.txt
python main.py
```

`run_bot.bat` 用于 Windows 计划任务，输出日志到 `logs/` 目录。

### GitHub Actions（远程）

通过 `.github/workflows/daily_news.yml` 定时触发，密钥存于 GitHub Secrets。

## 网络要求

| 服务 | 访问方式 |
|------|---------|
| RSS 源 | 直连 |
| Bing 搜索 | 直连 |
| Google News | 需代理（`HTTPS_PROXY`） |
| DeepSeek API | 直连 |
| Telegram API | 需代理（`HTTPS_PROXY`） |

## 依赖

| 包 | 用途 |
|----|------|
| `feedparser` | 解析 RSS/Atom 源 |
| `requests` | HTTP 请求（搜索、API 调用） |
| `python-dotenv` | 加载 `.env` 环境变量 |
