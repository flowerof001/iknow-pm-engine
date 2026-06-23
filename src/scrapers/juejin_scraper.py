"""掘金 (Juejin) 爬虫 — 获取 AI 相关热门中文技术文章"""
from typing import Optional
import requests


class JuejinScraper:
    """通过掘金推荐流 API 获取文章，过滤 AI 相关内容"""

    API = "https://api.juejin.cn/recommend_api/v1/article/recommend_all_feed"
    # AI 相关中文关键词
    AI_KEYWORDS = [
        "ai", "AI", "人工智能", "机器学习", "深度学习", "大模型",
        "大语言模型", "LLM", "GPT", "ChatGPT", "OpenAI", "Claude", "Gemini",
        "Copilot", "Cursor", "Codex", "Agent", "智能体", "RAG",
        "Prompt", "提示词", "AIGC", "生成式", "Transformer", "Diffusion",
        "微调", "Fine-tune", "LoRA", "向量", "Embedding", "langchain",
        "Llama", "DeepSeek", "通义", "文心", "混元", "豆包", "Kimi",
        "神经网络", "自动驾驶", "机器人", "具身智能",
        "MCP", "Model Context Protocol", "SDK", "多模态", "视觉",
        "OCR", "语音", "nlp", "NLP", "自然语言",
    ]

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Origin": "https://juejin.cn",
            "Referer": "https://juejin.cn/",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def _is_ai_related(self, title: str, brief: str = "") -> bool:
        """判断文章是否 AI 相关"""
        text = f"{title} {brief}".lower()
        for kw in self.AI_KEYWORDS:
            if kw.lower() in text:
                return True
        return False

    def _format_article(self, article_info: dict) -> dict:
        """格式化为标准输出"""
        tags = [t.get("tag_name", "") for t in article_info.get("tags", [])]
        return {
            "title": article_info.get("title", ""),
            "summary": (article_info.get("brief_content", "") or "")[:300],
            "url": f"https://juejin.cn/post/{article_info.get('article_id', '')}",
            "author": article_info.get("author_user_info", {}).get("user_name", ""),
            "category": article_info.get("category_info", {}).get("category_name", ""),
            "tags": tags,
            "views": article_info.get("article_info", {}).get("view_count", 0),
            "likes": article_info.get("article_info", {}).get("digg_count", 0),
            "comments": article_info.get("article_info", {}).get("comment_count", 0),
            "published": article_info.get("article_info", {}).get("ctime", ""),
            "source": "juejin",
        }

    def fetch(self, limit: int = 20, cursor: str = "0") -> list[dict]:
        """
        获取掘金推荐流文章
        limit: 每次请求数量
        cursor: 分页游标
        """
        payload = {
            "id_type": 2,
            "sort_type": 200,  # 热门排序
            "cursor": cursor,
            "limit": limit,
        }

        try:
            resp = self.session.post(
                self.API, json=payload, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[掘金] 请求失败: {e}")
            return []

        if data.get("err_no") != 0:
            print(f"[掘金] API 错误: {data.get('err_msg', 'unknown')}")
            return []

        items = data.get("data", [])
        if not items:
            print("[掘金] 无返回数据")
            return []

        results = []
        total = 0
        for item in items:
            total += 1
            article_info = item.get("item_info", {}).get("article_info", {})
            if not article_info:
                continue

            title = article_info.get("title", "")
            brief = article_info.get("brief_content", "")

            if not self._is_ai_related(title, brief):
                continue

            results.append(self._format_article(article_info))

        print(f"[掘金] 获取 {total} 篇，AI 相关 {len(results)} 篇")
        return results

    def fetch_multi_page(self, pages: int = 2, per_page: int = 20) -> list[dict]:
        """多页获取（每页用新 cursor）"""
        all_results = []
        cursor = "0"
        for _ in range(pages):
            results = self.fetch(limit=per_page, cursor=cursor)
            all_results.extend(results)
            if len(results) < per_page:
                break
            # 用返回的最后一条的 cursor（简化处理：递增）
            cursor = str(int(cursor) + per_page)
        return all_results


# 独立运行测试
if __name__ == "__main__":
    scraper = JuejinScraper()
    articles = scraper.fetch(limit=20)
    print(f"\n获取 {len(articles)} 篇 AI 相关掘金文章")
    print("-" * 60)
    for a in articles[:10]:
        tags = ", ".join(a["tags"][:3])
        print(f"  👁 {a['views']:>5} 👍{a['likes']:>3}  [{a.get('category', '')}] {a['title'][:60]}")
        print(f"         标签: {tags}")
        print()
