"""AI 行业新闻爬虫 — 36氪、机器之心、量子位"""
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup


class NewsScraper:
    """爬取 AI 行业新闻源"""

    SOURCES = {
        "36kr": {
            "url": "https://36kr.com/search/articles/人工智能",
            "item_selector": "div.article-item-wrapper",
            "title_selector": "a.article-item-title",
            "summary_selector": "a.article-item-description",
            "link_attr": "href",
        },
        "jiqizhixin": {
            "url": "https://www.jiqizhixin.com/articles",
            "item_selector": "div.article-item",
            "title_selector": "h2 a, h3 a",
            "summary_selector": "p",
            "link_attr": "href",
        },
    }

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def fetch_36kr(self) -> list[dict]:
        """爬取 36氪 AI 频道"""
        return self._fetch("36kr")

    def fetch_jiqizhixin(self) -> list[dict]:
        """爬取机器之心"""
        return self._fetch("jiqizhixin")

    def _fetch(self, source_key: str) -> list[dict]:
        cfg = self.SOURCES.get(source_key)
        if not cfg:
            return []

        try:
            resp = self.session.get(cfg["url"], timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            print(f"[{source_key}] 请求失败: {e}")
            return []

        articles = []
        items = soup.select(cfg["item_selector"])

        for item in items[:20]:
            title_el = item.select_one(cfg["title_selector"])
            summary_el = item.select_one(cfg["summary_selector"])

            title = title_el.get_text(strip=True) if title_el else ""
            summary = summary_el.get_text(strip=True) if summary_el else ""
            link = title_el.get(cfg["link_attr"], "") if title_el else ""
            if link and not link.startswith("http"):
                if source_key == "36kr":
                    link = "https://36kr.com" + link

            if not title:
                continue

            articles.append({
                "title": title[:200],
                "summary": summary[:300],
                "url": link,
                "source": source_key,
            })

        return articles

    def fetch_all(self) -> list[dict]:
        """聚合所有新闻源"""
        all_articles = []
        all_articles.extend(self.fetch_36kr())
        all_articles.extend(self.fetch_jiqizhixin())
        return all_articles


# 独立运行测试
if __name__ == "__main__":
    scraper = NewsScraper()
    articles = scraper.fetch_all()
    print(f"获取 {len(articles)} 篇新闻")
    for a in articles[:10]:
        print(f"  [{a['source']}] {a['title'][:80]}")
