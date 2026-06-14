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
    ├── search_keywords()         # 每个关键词分别搜索 Google News RSS + Bing 网页
    ├── summarize_keyword_tracking()  # 分组模式：每组独立 AI 调用 → 综合风险评估
    │                               # 平铺模式：单次 AI 调用（筛选、情感、风险）
    └── send_telegram()
```

## 模块详解

### 1. 配置加载

- 通过 `python-dotenv` 从 `.env` 加载环境变量
- `_parse_list()` 将逗号分隔字符串转为列表
- 必需项：`DEEPSEEK_API_KEY`、`TG_BOT_TOKEN`、`TG_CHAT_ID`、`RSS_FEEDS`、`INTERESTS`
- 可选项：`SEARCH_KEYWORD_GROUPS`（格式：`组名:关键词1,关键词2;组名:关键词3`，与 `SEARCH_KEYWORDS` 二选一，分组模式会为每组单独调用 AI 并生成综合风险评估）、`SEARCH_KEYWORDS`（逗号分隔，为空则跳过关键词追踪，与 `SEARCH_KEYWORD_GROUPS` 二选一）、`HTTPS_PROXY`、`SEARCH_TIME_RANGE`（时间范围，默认 `m`=月）、`SEARCH_MAX_RESULTS`（默认 10）、`TEST_MODE`（设为 `1` 则不发送 Telegram，输出保存到 `output/` 目录）

### 2. AI 日报

**fetch_all_news()** — RSS 抓取
- 使用 `feedparser` 解析每个 RSS 源
- 每源最多取 10 条（`MAX_ITEMS_PER_FEED`），总计不超过 60 条（`MAX_TOTAL_ITEMS`）
- 字段：title、link、summary（去 HTML 标签，截取前 300 字）、published

**summarize_with_deepseek()** — AI 摘要
- 将所有新闻拼接为编号列表，附带用户兴趣关键词
- Prompt 要求：筛选 10 条最相关新闻 → 中文摘要 → 影响分析 → ★ 评分排序
- 模型 `deepseek-chat`，temperature=0.3，max_tokens=4000
- 失败时降级为原始列表 (`_build_fallback_report`)

### 3. 关键词追踪

**search_keywords()** — 双引擎搜索
- 支持两种模式：**分组模式**（`SEARCH_KEYWORD_GROUPS`，格式 `组名:关键词1,关键词2;组名:关键词3`）和**平铺模式**（`SEARCH_KEYWORDS`，逗号分隔），两者二选一
- **Google News RSS**：`https://news.google.com/rss/search?q=<keyword>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans`，代码层按 `SEARCH_TIME_RANGE` 过滤日期
- **Bing 网页搜索**：直连 `www.bing.com`，正则解析 `<li class="b_algo">` 块提取标题/链接/摘要，通过 `tbs=qdr:m` 限制时间范围
- 每条结果标注来源 `news` 或 `web`，分组模式下额外标注所属分组

**summarize_keyword_tracking()** — 舆情分析

- **平铺模式**（未设置 `SEARCH_KEYWORD_GROUPS`）：单次 AI 调用，使用 `keyword_tracking_flat` prompt
  - 筛选 5-8 条 → 中文摘要 → 情感判定（正面/负面/中性）
  - 检测投诉、维权、经营异常等负面信息，用 ⚠️ 标注
  - 输出综合风险评估（低/中/高）

- **分组模式**（设置了 `SEARCH_KEYWORD_GROUPS`）：N+1 次 AI 调用
  - 每个分组单独调用，使用 `keyword_tracking_group` prompt（筛选 2-3 条，不包含风险评估）
  - 可在 `prompts.json` 中配置 `group_{组名}` 自定义 prompt 覆盖默认
  - 最后调用 `risk_assessment` prompt 综合所有分组结果生成整体风险评估

### 4. Telegram 推送

- 使用 Bot API `sendMessage`，`parse_mode: "Markdown"`
- 超 4000 字符自动按行拆分为多条消息 (`_split_text`)
- Markdown 解析失败时自动降级为纯文本发送 (`_send_fallback`)

## 运行方式

### 本地

```bash
pip install -r requirements.txt
python main.py                      # 正常模式，发送到 Telegram
set TEST_MODE=1 && python main.py   # 测试模式，输出到 output/ 目录
```

`run_bot.bat` 用于 Windows 计划任务，输出日志到 `logs/` 目录。

### GitHub Actions（远程）

> 暂未实现，计划通过 `.github/workflows/daily_news.yml` 定时触发，密钥存于 GitHub Secrets。

## 网络要求

| 服务 | 访问方式 |
|------|---------|
| RSS 订阅源（`RSS_FEEDS`） | 直连 |
| Bing 搜索 | 直连 |
| Google News RSS 搜索 | 需代理（`HTTPS_PROXY`） |
| DeepSeek API | 直连 |
| Telegram API | 需代理（`HTTPS_PROXY`） |

## AI 交互详解

### 对话模式

两次独立的 API 调用（分组模式下为 N+2 次），每次都是一轮问答（无上下文、无历史），通过精心设计的 Prompt 控制输出。

### 调用 1：AI 日报（`summarize_with_deepseek`）

**提供给 AI 的信息：**
```text
你是一个专业的 AI 和科技领域新闻编辑。

用户的兴趣领域：{interests}

以下是今天抓取的新闻列表：

1. [OpenAI Announces GPT-5](https://openai.com/...)
   摘要: OpenAI today announced the next generation...
2. [LangChain Launches New Agent Framework](https://...)
   摘要: A new open-source framework for building...
（共 40-60 条）

请完成以下任务：
1. 从中筛选出与用户兴趣最相关、最重要的 10 条新闻
2. 用中文为每条生成简洁摘要（1-2 句）
3. 给出简短的影响分析
4. 按重要性排序，用 ★ 评分（最高 ★★★★★，最低 ★★★☆☆）
5. 每条新闻必须保留原始链接

输出格式严格为（不要添加额外的前言后语）：

【AI 日报】2026年06月14日

★★★★★ **[标题](链接)**
摘要：...
影响：...

★★★★☆ **[标题](链接)**
摘要：...
影响：...
```

**期望得到的信息（AI 返回的 Markdown 直接推送 Telegram）：**
```text
【AI 日报】2026年06月14日

★★★★★ **[OpenAI 发布 GPT-5](https://openai.com/...)**
摘要：OpenAI 正式发布 GPT-5 大模型，推理能力较上代提升 3 倍...
影响：将推动整个 AI 应用生态升级

★★★★☆ **[LangChain 推出新 Agent 框架](https://...)**
摘要：...
影响：...
```

> 链接嵌入标题 Markdown 语法 `[标题](url)` 中，Telegram 渲染后只显示可点击的标题文字，不显示原始 URL。

---

### 调用 2：关键词追踪（`summarize_keyword_tracking`）

支持两种模式：

#### 平铺模式（仅设置 `SEARCH_KEYWORDS`）

**提供给 AI 的信息：**
```text
你是一个信息监控助手，帮助用户追踪特定关键词的最新动态。

追踪关键词：关键词A, 关键词B, 关键词C

以下是今天从网络搜索（新闻、论坛、社交媒体）中抓取到的相关信息：

1. [某产品出现大量退款投诉](https://...) [web]
   摘要: 近期不少用户在社交媒体上反映...
（共 20-40 条，每条约 200 字摘要）

请完成以下任务：
1. 筛选出最重要的 5-8 条信息
2. 用中文为每条生成简洁摘要（1-2 句）
3. 按重要性排序，用 ★ 评分
4. 判断情感倾向（正面/负面/中性）
5. ⚠️ 如果发现负面信息（投诉、维权、经营异常、资金链、跑路等），必须用 ⚠️ 特别标注并说明
6. 最后给出综合风险评估（低/中/高）

输出格式严格为（不要添加额外的前言后语）：

🔍 关键词追踪 2026年06月14日

追踪：关键词A, 关键词B, 关键词C

★★★★★ **[标题](链接)**
摘要：...
来源：新闻/论坛/社交媒体
情感：正面/负面/中性

⚠️ 风险提示：（如有）

综合风险评估：低/中/高
```

#### 分组模式（设置 `SEARCH_KEYWORD_GROUPS`）

每组独立调用 AI（使用 `keyword_tracking_group` prompt），筛选 2-3 条，格式如下：

```
## {组名}

★★★★★ **[标题](链接)**
摘要：...
来源：新闻/论坛/社交媒体
情感：正面/负面/中性
```

所有分组完成后，额外调用 `risk_assessment` prompt 综合生成整体风险评估。可通过 `prompts.json` 中的 `group_{组名}` 键为特定分组覆盖自定义 prompt。

**期望得到的信息：**
```text
🔍 关键词追踪 2026年06月14日
追踪：关键词A, 关键词B, 关键词C

★★★★★ **[某产品被指虚假宣传](https://...)**
摘要：...
来源：社交媒体
情感：负面

⚠️ 风险提示：近期出现较多用户投诉，建议关注后续处理进展。

综合风险评估：中
```

---

### 技术参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | `deepseek-chat` | DeepSeek 标准对话模型 |
| temperature | 0.3 | 低随机性，保证输出稳定 |
| max_tokens | 4000 | 足够生成完整日报 |
| 接口 | `https://api.deepseek.com/v1/chat/completions` | OpenAI 兼容格式 |
| 上下文 | 无（每次独立调用） | 不携带历史对话 |

### 容错机制

AI 摘要失败时，直接发送原始新闻列表（`_build_fallback_report` / `_build_tracking_fallback`），格式为编号 + 链接。

### 上下文大小分析

> deepseek-chat 上下文窗口为 **128K tokens**，以下均为安全范围。

**AI 日报 Prompt 体积：**

```
MAX_TOTAL_ITEMS = 60 条新闻
每条：标题(~10 tokens) + 链接(~20 tokens) + 摘要(~100 tokens) ≈ 130 tokens
新闻列表：60 × 130 ≈ 7,800 tokens
系统指令 + 格式要求 ≈ 300 tokens
─────────────────────────────
总计 ≈ 8,000 tokens（约 < 128K 的 6%）
```

**关键词追踪 Prompt 体积：**

```
假设 3 个关键词，每个返回 ~15 条结果 = 45 条上限（取 30~45 条）
每条：标题(~10) + 链接(~20) + 摘要(~50) + 来源标记(~2) ≈ 82 tokens
新闻列表：45 × 82 ≈ 3,700 tokens
系统指令 + 格式要求 ≈ 400 tokens
─────────────────────────────
总计 ≈ 4,100 tokens（约 < 128K 的 3%）
```

**结论：** 当前规模下没有任何上下文溢出风险。即使 RSS 源数量和关键词数量大幅增加，也有充足余量。

---

## 提示词自定义

所有 AI 提示词定义在 `main.py` 的 `PROMPT_DEFAULTS` 字典中，可通过 `prompts.json` 文件覆盖。

### 工作原理

1. `_load_prompts()` 从 `prompts.json` 加载自定义提示词，与默认值合并
2. `_build_prompt(key, **kwargs)` 通过 key 获取模板，用 `str.format()` 替换占位符
3. 如果 `prompts.json` 不存在或解析失败，回退使用 `PROMPT_DEFAULTS`

### 支持的 key

| Key | 用途 |
|-----|------|
| `daily_news` | AI 日报 prompt |
| `keyword_tracking_group` | 分组追踪 prompt（每个分组独立调用）|
| `keyword_tracking_flat` | 平铺追踪 prompt（不分组的模式）|
| `risk_assessment` | 综合风险评估 prompt（仅分组模式使用）|
| `group_{组名}` | 自定义分组 prompt，覆盖 `keyword_tracking_group` |

### 示例

`prompts.example.json` 提供了完整的模板参考，复制为 `prompts.json` 后可按需修改。

自定义分组 prompt 示例（`prompts.json`）：
```json
{
  "group_游戏": "你是游戏行业观察员，请从以下信息中筛选 2-3 条最重要的动态..."
}
```

### 支持的占位符

| 占位符 | 用于 |
|--------|------|
| `{interests}` | `daily_news` |
| `{date}` | `daily_news`, `keyword_tracking_flat` |
| `{items}` | `daily_news`, `keyword_tracking_group`, `keyword_tracking_flat` |
| `{group}` | `keyword_tracking_group` |
| `{keywords}` | `keyword_tracking_group`, `keyword_tracking_flat` |
| `{groups_summary}` | `risk_assessment` |

## 依赖

| 包 | 用途 |
|----|------|
| `feedparser` | 解析 RSS/Atom 源 |
| `requests` | HTTP 请求（搜索、API 调用） |
| `python-dotenv` | 加载 `.env` 环境变量 |
