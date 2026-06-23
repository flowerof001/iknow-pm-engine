"""Hacker News 爬虫 — 获取 AI 相关热门故事"""
from typing import Optional
import requests
from datetime import datetime


class HNScraper:
    """通过 Firebase API 爬取 Hacker News 热门故事，过滤 AI 相关内容"""

    BASE = "https://hacker-news.firebaseio.com/v0"
    # AI 相关关键词
    AI_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "llm", "gpt", "claude", "gemini", "openai", "anthropic",
        "transformer", "neural network", "nlp", "computer vision",
        "generative", "rag", "agent", "vector", "embedding",
        "fine-tun", "langchain", "llama", "mistral", "diffusion",
        "stable diffusion", "sora", "copilot", "cursor",
        "robot", "autonomous", "self-driving",
    ]

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "AI-Career-Engine/1.0",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def _get_top_story_ids(self, limit: int = 50) -> list[int]:
        """获取热门故事 ID 列表"""
        try:
            resp = self.session.get(
                f"{self.BASE}/topstories.json", timeout=10
            )
            resp.raise_for_status()
            ids = resp.json()
            return ids[:limit]
        except Exception as e:
            print(f"[HN] 获取故事列表失败: {e}")
            return []

    def _get_story(self, story_id: int) -> Optional[dict]:
        """获取单个故事详情"""
        try:
            resp = self.session.get(
                f"{self.BASE}/item/{story_id}.json", timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[HN] 获取故事 {story_id} 失败: {e}")
            return None

    def _is_ai_related(self, story: dict) -> bool:
        """判断故事是否 AI 相关"""
        text = f"{story.get('title', '')} {story.get('text', '')}".lower()
        for kw in self.AI_KEYWORDS:
            if kw in text:
                return True
        return False

    def _format_story(self, story: dict) -> dict:
        """格式化故事为标准输出"""
        return {
            "title": story.get("title", ""),
            "url": story.get("url", f"https://news.ycombinator.com/item?id={story.get('id', '')}"),
            "summary": (story.get("text", "") or "")[:300],
            "score": story.get("score", 0),
            "descendants": story.get("descendants", 0),  # 评论数
            "by": story.get("by", ""),
            "published": datetime.fromtimestamp(
                story.get("time", 0)
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "hackernews",
        }

    def fetch(self, max_items: int = 50, ai_only: bool = True) -> list[dict]:
        """
        获取 HN 热门故事
        max_items: 最大获取数量
        ai_only: 是否仅返回 AI 相关内容
        """
        ids = self._get_top_story_ids(limit=max_items)
        if not ids:
            return []

        results = []
        fetched = 0
        for sid in ids:
            story = self._get_story(sid)
            if not story:
                continue
            fetched += 1

            if ai_only and not self._is_ai_related(story):
                continue

            results.append(self._format_story(story))

        print(f"[HN] 获取 {fetched} 个故事，其中 AI 相关 {len(results)} 个")
        return results

    def fetch_all(self, max_items: int = 50) -> list[dict]:
        """获取全部热门（不限制 AI）"""
        return self.fetch(max_items=max_items, ai_only=False)


# 独立运行测试
if __name__ == "__main__":
    scraper = HNScraper()
    stories = scraper.fetch(max_items=30)
    print(f"\n获取 {len(stories)} 条 AI 相关 HN 故事")
    print("-" * 50)
    for s in stories[:8]:
        print(f"  ▲{s['score']:>4} 💬{s['descendants']:>3}  {s['title'][:70]}")
        if s.get("summary"):
            print(f"         {s['summary'][:100]}...")
        print(f"         {s['url'][:80]}")
        print()
