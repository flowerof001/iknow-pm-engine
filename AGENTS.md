# iKnow — AI 产品经理内容引擎

## 项目概述
面向中国互联网产品经理的 AI 内容引擎。自动采集 7 路信息源，通过 LLM 生成 5 个 PM 专属栏目的深度内容，并改写为 6 个平台的发布版本。

## 技术栈
- **后端**: FastAPI (admin/server.py), 端口 8800
- **前端**: SPA 仪表盘 (admin/static/index.html), Tailwind CSS CDN + 原生 JS
- **数据库**: SQLite (admin/iknow.db), 通过 admin/data.py 操作
- **AI**: OpenAI 兼容 API (当前用 DeepSeek)
- **部署**: Render (render.yaml)

## 目录结构
```
admin/
├── server.py          # FastAPI 后端 (16 个 API 路由 + SSE)
├── data.py            # SQLite 数据层
├── model_config.json  # 业务→模型映射配置
├── model_registry.json # 可用模型注册表
└── static/
    └── index.html     # 前端 SPA (仪表盘/流水线/内容管理/归档 4 Tab)

src/
├── pipeline.py         # 主流水线 (采集→路由→生成→多平台，全隔离)
├── config.py           # 全局配置
├── model_resolver.py   # 模型解析器
├── utils.py            # 🆕 共享工具（@retry 重试 + Logger）
├── scrapers/           # 7 路数据采集
│   ├── woshipm_scraper.py   # 🆕 人人都是产品经理 RSS
│   ├── github_scraper.py    # GitHub AI 仓库
│   ├── arxiv_scraper.py     # arXiv 论文
│   ├── hn_scraper.py        # Hacker News
│   ├── juejin_scraper.py    # 掘金 AI 文章
│   ├── v2ex_scraper.py      # V2EX 热帖
│   └── news_scraper.py      # 36kr/机器之心 (可能反爬失效)
├── generators/
│   ├── pm_prompts.py        # PM 专属 5 栏目 Prompt
│   └── content_generator.py # LLM 调用封装
├── adapters/
│   └── multi_platform.py    # 6 平台版本改写
└── images/                  # FLUX 图片生成
```

## 5 个 PM 栏目
| 栏目 key | 名称 | 定位 |
|---|---|---|
| ai_product_radar | AI产品经理岗位雷达 | 大厂AI PM岗位变化、技能需求 |
| ai_product_signal | 本周AI产品信号 | 新技术/产品对PM的影响 |
| pm_toolbox | PM AI 提效工具箱 | 可复制的Prompt/工作流/模板 |
| ai_product_deepdive | AI产品深度拆解 | 深度拆解一个AI产品 |
| pm_practice_notes | 产品实战笔记 | 精选PM实战经验萃取 |

## 多平台版本
微信公众号 / 即刻 / 小红书 / 知乎 / 脉脉 / 微信群

## API 路由
```
GET  /api/stats            - 仪表盘统计
POST /api/pipeline/run     - 启动流水线
POST /api/pipeline/cron    - 定时触发流水线（供外部 Cron 调用）
GET  /api/pipeline/stream  - SSE 实时进度
GET  /api/pipeline/runs    - 历史运行列表
GET  /api/scheduler        - 调度器配置（开关/时间/上次状态）
PUT  /api/scheduler        - 更新调度器配置
GET  /api/contents         - 内容列表
PUT  /api/contents/{id}    - 编辑内容
DELETE /api/contents/{id}  - 删除内容
GET  /api/archive/dates    - 有内容的日期列表
GET  /api/archive/{date}   - 按日期归档
GET  /api/config           - 模型配置
GET  /api/models           - 可用模型列表
```

## 环境变量 (.env)
```
LLM_API_KEY=sk-xxx        # DeepSeek API Key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
REPLICATE_API_TOKEN=r8_xxx # FLUX 图片生成
ZHIPU_API_KEY=xxx          # 智谱 GLM (备用)
```

## 运行方式
```bash
# 本地
python3 -m uvicorn admin.server:app --host 0.0.0.0 --port 8800

# 生产 (Render)
uvicorn admin.server:app --host 0.0.0.0 --port $PORT
```

## GitHub & 部署
- **Repo**: https://github.com/flowerof001/iknow
- **Render**: https://iknow-pm-engine.onrender.com
- **Render Dashboard**: https://dashboard.render.com

## 已生成内容 (2026-06-24)
- Run #2 成功，5 篇共 16,952 字
- 输出目录: output/2026-06-24/

## 待办 / 可优化项
1. ✅ Render 环境变量已配置（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），线上流水线已验证通过
2. ✅ news_scraper 已重构：36kr/机器之心移除（JS 渲染不可抓），改用少数派 RSS + AI 关键词过滤
3. ✅ 前端 Markdown 预览已升级为 marked.js + highlight.js，支持代码高亮
4. ✅ 定时任务 (cron) 完成：/api/pipeline/cron + 后台调度器 + 前端开关 + Render Cron Job
5. 🔒 ProductHunt 被 Cloudflare 防护，当前无法抓取
6. 🔒 V2EX 的 "ai" 节点不存在 (404)，已 fallback 到 programmer/create 节点
7. ✅ 已通过 marked.js 解决，表格/代码块/引用均正常渲染
8. **[想法]** 增加内容发布到飞书/微信的自动化
9. **[想法]** 增加用户反馈/评分机制来优化 Prompt
10. ✅ Git push HTTPS 挂起已解决 → 切换 SSH + ~/.zshrc 配置 NO_PROXY
11. ✅ GitHub Actions 保活每 5 分钟 ping，防 Render 休眠

## 已完善 (2026-06-24)
- ✅ Markdown 渲染升级为 marked.js + highlight.js
- ✅ 内容下载按钮（导出 .md）
- ✅ news_scraper 重构（36kr/机器之心→少数派 RSS）
- ✅ ContentGenerator 改用 PM_PROMPTS（修复生成失败）
- ✅ 前端 4 Tab SPA 仪表盘完整可用
- ✅ 5 篇 PM 内容成功生成（16,952 字）

## 已完善 (2026-06-29)
- ✅ Render 环境变量配置完成（DeepSeek API）
- ✅ 线上流水线验证通过（7 路源 101 条数据 → pm_toolbox 3089 字 + 6 平台版本）
- ✅ Render API 自动部署触发成功
- ✅ 线上 Dashboard: https://iknow-pm-engine.onrender.com 正常运行
- ✅ 定时任务系统：/api/pipeline/cron + 后台调度器 + 前端开关 + Render Cron Job
- ✅ Pipeline 健壮性：scraper 隔离 + LLM 指数退避重试 (3次) + 单栏目失败不阻塞
- ✅ 结构化日志：src/utils.py (@retry 装饰器 + Logger)
- ✅ GitHub 远程切换为 SSH（解决代理导致 git push 挂起）
- ✅ GitHub Actions 保活：每 5 分钟 ping 防 Render 休眠
- ✅ 新增目录：src/utils.py / .github/workflows/keepalive.yml
