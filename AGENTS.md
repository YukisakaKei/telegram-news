# AGENTS.md — telegram-news AI 代理配置

## 项目
Telegram AI 新闻机器人：抓取 RSS + 网页搜索，通过 DeepSeek 摘要，发送到 Telegram。

## 隐私规则
**以下内容严禁出现在任何提交到 GitHub 的文件中（包括 AGENTS.md 本身）。**

### 1. 密钥与账号
- API 密钥（`sk-*`）、Telegram Bot Token（`数字:字母` 格式）、Chat ID、Webhook URL 等所有认证凭据，**只能存在于 `.env`**。
- `.env.example` 中必须使用假值：`sk-your-key`、`123456:ABC`、`123456789`。

### 2. 关键词与消息来源
- 搜索关键词（`SEARCH_KEYWORDS`、`SEARCH_KEYWORD_GROUPS`）、RSS 订阅 URL、目标网站、公司名、品牌名、人名等反映用户关注方向的内容，**只能存在于 `.env`**。
- `INTERESTS` 同样反映用户关注方向，**只能存在于 `.env`**。
- `.env.example` 中的 `SEARCH_KEYWORDS`/`SEARCH_KEYWORD_GROUPS` 必须使用公开通用示例（如 `国际服 蔚蓝档案,日服 蔚蓝档案`）。
- `.env.example` 中的 `INTERESTS` 也必须使用通用示例（如 `AI,LLM,Technology`）。
- `RSS_FEEDS` 示例也只能使用公开知名 RSS 源，不得包含用户私有订阅。

### 3. 兜底条款
- **任何可能推断出使用者个人信息、账号信息、关注方向、地理位置、设备信息、网络环境的内容，一律不得提交。**
- 包括但不限于：真实 IP、代理地址、用户名、手机号、邮箱、搜索历史、聊天记录、关注列表、自定义配置中与个人身份/偏好相关的一切。

## 环境变量与 .env
- 所有密钥存放在 `.env`（已 gitignore），通过 `python-dotenv` 加载。
- `.env.example` 会上传到 GitHub，只能包含占位/假值。
- `requests` 库会自动从环境变量读取 `HTTPS_PROXY`/`HTTP_PROXY`。

## 网络
国内运行环境：
- **Bing**（`www.bing.com`）— 直连可达，无需代理。
- **Google 服务**（`news.google.com` 等）— 需代理。
- **Telegram API**（`api.telegram.org`）— 需代理。
- **DeepSeek API**（`api.deepseek.com`）— 直连可达。
- 代理通过 `.env` 中的 `HTTPS_PROXY=http://127.0.0.1:7890` 设置。

## 搜索关键词
- `SEARCH_KEYWORDS` 中用逗号分隔不同组合，所有关键词混在一起搜索和总结。
- `SEARCH_KEYWORD_GROUPS` 支持分组追踪：`组名:关键词1,关键词2;组名:关键词3`。每个组独立调用 AI 摘要，提高质量。
- 组合内空格表示 AND 搜索（如 `国际服 蔚蓝档案` 同时搜索两个词）。
- 每个组合分别通过 Google News RSS 和 Bing 网页搜索。

## 测试
```bash
pip install -r requirements.txt
# 正常模式
python main.py
# 测试模式（消息不发送 Telegram，保存到 output/ 目录）
set TEST_MODE=1 && python main.py     # Windows
TEST_MODE=1 python main.py            # macOS/Linux
```

## 文件
| 文件 | 用途 |
|------|------|
| `main.py` | 全部机器人逻辑 |
| `.env` | 密钥（gitignored） |
| `.env.example` | 模板（已提交，无密钥） |
| `requirements.txt` | 依赖 |
| `run_bot.bat` | Windows 计划任务入口 |
| `ARCHITECTURE.md` | 项目逻辑文档 |
| `output/` | 测试模式输出（gitignored） |
| `logs/` | 运行日志（gitignored） |
