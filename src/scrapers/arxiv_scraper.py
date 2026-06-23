"""arXiv AI 论文爬虫"""
import re
from typing import Optional
import requests
import xml.etree.ElementTree as ET


class ArxivScraper:
    """爬取 arXiv cs.AI 与 cs.CL 分类最新论文"""

    BASE = "http://export.arxiv.org/api/query"

    CATEGORIES = {
        "cs.AI": "Artificial Intelligence",
        "cs.CL": "Computation and Language (NLP)",
        "cs.CV": "Computer Vision",
    }

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理
        self.session.headers.update({"User-Agent": "AI-Career-Engine/1.0"})
        if proxy:
            self.session.proxies = {"http": proxy}

    def _build_url(self, categories: list[str], max_results: int = 20) -> str:
        cat_str = "+OR+".join(f"cat:{c}" for c in categories)
        return (
            f"{self.BASE}?search_query={cat_str}"
            f"&start=0&max_results={max_results}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )

    def _ns(self, tag: str) -> str:
        return f"{{http://www.w3.org/2005/Atom}}{tag}"

    def fetch(self, max_results: int = 20) -> list[dict]:
        """返回最新 AI 论文列表"""
        url = self._build_url(list(self.CATEGORIES.keys()), max_results)
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except Exception as e:
            print(f"[arXiv] 请求失败: {e}")
            return []

        papers = []
        for entry in root.findall(self._ns("entry")):
            title_el = entry.find(self._ns("title"))
            summary_el = entry.find(self._ns("summary"))
            link_el = entry.find(self._ns("id"))
            published_el = entry.find(self._ns("published"))

            title = (title_el.text or "").strip().replace("\n", " ")
            summary = (summary_el.text or "").strip().replace("\n", " ")[:400]
            arxiv_id = (link_el.text or "").strip()

            # 提取分类
            cats = []
            for cat_el in entry.findall(self._ns("category")):
                term = cat_el.get("term", "")
                if term in self.CATEGORIES:
                    cats.append(term)

            papers.append({
                "title": title,
                "summary": summary,
                "url": arxiv_id,
                "pdf_url": arxiv_id.replace("abs", "pdf") if "abs" in arxiv_id else "",
                "published": (published_el.text or "")[:10] if published_el is not None else "",
                "categories": cats,
                "source": "arxiv",
            })

        return papers


# 独立运行测试
if __name__ == "__main__":
    scraper = ArxivScraper()
    papers = scraper.fetch(max_results=10)
    print(f"获取 {len(papers)} 篇论文")
    for p in papers[:5]:
        cats = ", ".join(p["categories"])
        print(f"  [{cats}] {p['title'][:80]}")
        print(f"         {p['summary'][:100]}...")
