"""GitHub Trending AI 仓库爬虫"""
import re
from datetime import datetime, timedelta
from typing import Optional
import requests


class GitHubScraper:
    """爬取 GitHub 上与 AI/ML 相关的热门仓库"""

    BASE = "https://api.github.com"

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-Career-Engine/1.0",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def _build_url(self, days_back: int = 3, per_page: int = 20) -> str:
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        return (
            f"{self.BASE}/search/repositories"
            f"?q=ai+artificial-intelligence+machine-learning+created:>={since}"
            f"&sort=stars&order=desc&per_page={per_page}"
        )

    def fetch(self, days_back: int = 3) -> list[dict]:
        """返回热门 AI 仓库列表"""
        url = self._build_url(days_back)
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as e:
            print(f"[GitHub] 请求失败: {e}")
            return []

        results = []
        for repo in items:
            results.append({
                "name": repo.get("full_name", ""),
                "url": repo.get("html_url", ""),
                "description": (repo.get("description") or "")[:300],
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language", ""),
                "topics": repo.get("topics", []),
                "created_at": repo.get("created_at", ""),
                "source": "github",
            })
        return results


# 独立运行测试
if __name__ == "__main__":
    scraper = GitHubScraper()
    repos = scraper.fetch(days_back=7)
    print(f"获取 {len(repos)} 个仓库")
    for r in repos[:5]:
        print(f"  ⭐{r['stars']:>6}  {r['name']:<40}  {r['description'][:80]}")
