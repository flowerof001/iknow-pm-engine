"""人人都是产品经理 RSS 爬虫 — PM 专属内容源"""
from typing import Optional
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import html


class WoshipmScraper:
    """通过 RSS Feed 抓取人人都是产品经理的文章，按分类过滤"""

    FEED_URL = "https://www.woshipm.com/feed"
    # 优先关注的分类
    PRIORITY_CATEGORIES = ["AI", "产品经理", "产品设计", "产品运营", "数据分析", "行业分析"]

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def _clean_html(self, text: str) -> str:
        """去除 HTML 标签"""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = html.unescape(clean)
        return clean.strip()

    def _extract_channel_title(self, description: str) -> tuple:
        """从 <description> 中提取文章摘要和分类（人人都是产品经理 RSS 特殊格式）"""
        # RSS <description> 格式: <![CDATA[<p>摘要内容</p><p>文章来自: <a href="...">分类名</a></p>]]>
        summary = re.sub(r'<[^>]+>', '', description)
        # 提取 "文章来自：" 之后的分类
        cat_match = re.search(r'文章来自[：:]\s*([^\s<]+)', description)
        channel = cat_match.group(1) if cat_match else ""
        # 清理摘要
        summary = re.sub(r'文章来自[：:].*$', '', summary).strip()
        return summary[:400], channel

    def fetch(self, max_items: int = 20) -> list[dict]:
        """抓取 RSS，返回格式化文章列表"""
        try:
            resp = self.session.get(self.FEED_URL, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            print(f"[人人] 请求失败: {e}")
            return []

        items = root.findall(".//item")
        results = []

        for item in items[:max_items]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")
            cat_els = item.findall("category")
            creator_el = item.find("{http://purl.org/dc/elements/1.1/}creator")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            raw_desc = desc_el.text if desc_el is not None else ""
            categories = [c.text for c in cat_els if c.text]

            summary, channel = self._extract_channel_title(raw_desc)

            # 优先级分类（AI 类优先，其他也保留）
            is_priority = any(c in self.PRIORITY_CATEGORIES for c in categories)
            if not summary:
                summary = self._clean_html(raw_desc)[:400]

            results.append({
                "title": title,
                "summary": summary,
                "url": link,
                "categories": categories,
                "channel": channel or (categories[0] if categories else ""),
                "author": creator_el.text if creator_el is not None else "",
                "published": pubdate_el.text if pubdate_el is not None else "",
                "is_ai_related": "AI" in categories or any(
                    kw in title for kw in ["AI", "人工智能", "大模型", "ChatGPT", "Claude", "Cursor", "Copilot"]
                ),
                "source": "woshipm",
            })

        ai_count = sum(1 for r in results if r["is_ai_related"])
        print(f"[人人] 获取 {len(results)} 篇，AI 相关 {ai_count} 篇")
        return results

    def fetch_ai_only(self, max_items: int = 20) -> list[dict]:
        """仅返回 AI 相关文章"""
        all_articles = self.fetch(max_items)
        return [a for a in all_articles if a["is_ai_related"]]


if __name__ == "__main__":
    s = WoshipmScraper()
    articles = s.fetch(15)
    print(f"\n人人都是产品经理 - 最新文章:")
    print("-" * 70)
    for a in articles[:10]:
        ai_tag = "🤖" if a["is_ai_related"] else "  "
        cats = "/".join(a["categories"][:2])
        print(f"  {ai_tag} [{cats:<20}] {a['title'][:55]}")
        print(f"          {a['summary'][:80]}...")
        print()
