# AI 新闻机器人 - 项目状态

## 已完成的工

1. **项目代码** — 全部完成，已推送到 GitHub
   - 仓库地址：https://github.com/YukisakaKei/telegram-news
   - 分支：`master`

2. **文件结构**：
   ```
   telegram-news/
   ├── main.py                          # 主脚本（RSS抓取 → DeepSeek摘要 → Telegram推送）
   ├── requirements.txt                 # feedparser + requests
   ├── .env.example                     # 环境变量参考
   ├── .gitignore
   └── .github/workflows/daily_news.yml # 定时/手动触发 workflow
   ```

3. **GitHub Secrets** — 用户已设置，共 5 个：
   | Secret | 说明 |
   |--------|------|
   | `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
   | `TG_BOT_TOKEN` | Telegram Bot Token |
   | `TG_CHAT_ID` | 用户 Chat ID |
   | `RSS_FEEDS` | RSS 源列表（逗号分隔） |
   | `INTERESTS` | 兴趣关键词（逗号分隔） |

## 当前问题：Workflow 未在 Actions 页面显示

- workflow 文件 `.github/workflows/daily_news.yml` 已推送并确认存在于 master 分支
- 文件内容与语法确认正确（包含 `workflow_dispatch` 手动触发 + `schedule` 定时触发）
- 但用户在 Actions 页面左侧边栏看不到 "Daily AI News" 这个 workflow
- 可能原因：刚推送需要几分钟延迟、或需要刷新页面（Ctrl+F5）
- 用户尝试点在侧边栏展开 "Show more workflows..."

## 调试步骤

1. 强制刷新 Actions 页面（Ctrl+F5），等1-2分钟
2. 在左侧 "Workflows" 区域查看是否出现 "Daily AI News"
3. 如果有 "Show more workflows..." 链接，点它展开
4. 如果仍然没有，检查仓库 Settings → Actions → General：
   - "Allow all actions and reusable workflows" 是否选中
   - "Allow GitHub Actions to create and approve pull requests" 是否启用
5. 确认当前分支是 `master`（默认分支），不是 `main`

## 测试方法

成功显示后，通过 Actions → Daily AI News → Run workflow → Run workflow 按钮手动触发测试。

## 成本预估

- GitHub Actions：免费（公开仓库无限使用）
- Telegram Bot API：免费
- DeepSeek API：约几元/月（每天调用一次）
