"""全局配置文件"""
import os
from pathlib import Path

# 可选加载 .env（不依赖 dotenv 包）
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        # 手动解析 .env 文件
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val


class Config:
    # ── LLM ──
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

    # ── 图片生成 ──
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")

    # ── 生成控制 ──
    DAILY_POSTS_PER_COLUMN = int(os.getenv("DAILY_POSTS_PER_COLUMN", "1"))
    OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(Path(__file__).parent.parent / "output")))

    # ── 代理 ──
    HTTP_PROXY = os.getenv("HTTP_PROXY", "")
    HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")

    # ── 信息源 RSS / API 端点 ──
    SOURCES = {
        "github_trending": {
            "url": "https://api.github.com/search/repositories?q=ai+artificial-intelligence+machine-learning+created:>{}&sort=stars&order=desc&per_page=20",
            "type": "api",
            "frequency": "daily",
        },
        "arxiv_ai": {
            "url": "http://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending",
            "type": "api",
            "frequency": "daily",
        },
        "arxiv_cl": {
            "url": "http://export.arxiv.org/api/query?search_query=cat:cs.CL&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending",
            "type": "api",
            "frequency": "daily",
        },
        "36kr_ai": {
            "url": "https://36kr.com/search/articles/人工智能?page=1",
            "type": "web",
            "frequency": "daily",
        },
        "jiqizhixin": {
            "url": "https://www.jiqizhixin.com/articles",
            "type": "web",
            "frequency": "daily",
        },
        "hackernews": {
            "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
            "type": "api",
            "frequency": "daily",
        },
        "producthunt": {
            "url": "https://www.producthunt.com/",
            "type": "web",
            "frequency": "daily",
        },
    }

    # ── 输出文件命名 ──
    OUTPUT_FILES = {
        "job_radar": "{date}_岗位替代雷达.md",
        "job_compass": "{date}_新岗位风向标.md",
        "weekly_learn": "{date}_本周必学.md",
        "tool_ranking": "{date}_AI工具实测榜.md",
        "case_study": "{date}_AI落地拆解.md",
        "template_lib": "{date}_提效模板库.md",
        "hiring_signals": "{date}_大厂用人信号.md",
        "salary_report": "{date}_薪资水位监测.md",
    }

    # ── 多平台配置 ──
    PLATFORMS = {
        "wechat": {"max_chars": 2500, "style": "深度长文"},
        "jike": {"max_chars": 500, "style": "讨论互动"},
        "xiaohongshu": {"max_chars": 300, "style": "情绪+信息图"},
        "zhihu": {"max_chars": 1800, "style": "专业分析"},
        "maimai": {"max_chars": 300, "style": "话题引导"},
        "wechat_group": {"max_chars": 250, "style": "精华摘要"},
    }


config = Config()
