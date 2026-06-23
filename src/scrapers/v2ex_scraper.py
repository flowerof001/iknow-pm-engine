"""V2EX 爬虫 — 获取 AI 相关热门讨论帖"""
from typing import Optional
import requests
from datetime import datetime


class V2EXScraper:
    """通过 V2EX API 获取热门话题，过滤 AI/技术相关内容"""

    API_BASE = "https://www.v2ex.com/api"

    # AI/技术相关节点名称
    AI_NODES = [
        "ai", "programmer", "ml", "data", "python",
        "create", "share", "programming", "cloud", "dev",
        "jobs", "career", "startup", "tech",
    ]

    # AI 相关中文关键词（用于标题过滤）
    AI_KEYWORDS = [
        "ai", "AI", "ChatGPT", "GPT", "LLM", "大模型", "大语言模型",
        "OpenAI", "Claude", "DeepSeek", "Cursor", "Copilot", "Codex",
        "机器学习", "深度学习", "人工智能", "神经网络", "Agent", "智能体",
        "Prompt", "AIGC", "RAG", "MCP", "多模态", "具身智能",
        "自动驾驶", "机器人", "编程", "程序员", "开发", "代码",
        "开源", "github", "工具", "自动化", "效率",
    ]

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        if proxy:
            self.session.proxies = {"https": proxy}

    def _is_ai_node(self, node: dict) -> bool:
        """判断节点是否 AI/技术相关"""
        name = node.get("name", "").lower()
        title = node.get("title", "").lower()
        for n in self.AI_NODES:
            if n == name or n in title:
                return True
        for kw in ["ai", "人工智能", "机器学习", "编程"]:
            if kw in title:
                return True
        return False

    def _is_ai_topic(self, title: str, content: str = "") -> bool:
        """判断帖子内容是否 AI 相关"""
        text = f"{title} {content}".lower()
        for kw in self.AI_KEYWORDS:
            if kw.lower() in text:
                return True
        return False

    def _format_topic(self, topic: dict) -> dict:
        """格式化为标准输出"""
        node = topic.get("node", {})
        member = topic.get("member", {})
        return {
            "title": topic.get("title", ""),
            "summary": (topic.get("content", "") or "")[:300],
            "url": topic.get("url", f"https://www.v2ex.com/t/{topic.get('id', '')}"),
            "node": node.get("title", ""),
            "author": member.get("username", ""),
            "replies": topic.get("replies", 0),
            "created": datetime.fromtimestamp(
                topic.get("created", 0)
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "v2ex",
        }

    def fetch_hot(self) -> list[dict]:
        """获取 V2EX 热门话题，自动过滤 AI 相关"""
        try:
            resp = self.session.get(
                f"{self.API_BASE}/topics/hot.json", timeout=15
            )
            resp.raise_for_status()
            topics = resp.json()
        except Exception as e:
            print(f"[V2EX] 获取热门失败: {e}")
            return []

        results = []
        for topic in topics:
            node = topic.get("node", {})
            title = topic.get("title", "")

            if self._is_ai_node(node) or self._is_ai_topic(title):
                results.append(self._format_topic(topic))

        print(f"[V2EX] 热门 {len(topics)} 条 → AI 相关 {len(results)} 条")
        return results

    def fetch_node(self, node_name: str, page: int = 1) -> list[dict]:
        """获取指定节点的最新帖子"""
        try:
            # 先获取节点 ID
            resp = self.session.get(
                f"{self.API_BASE}/nodes/show.json?name={node_name}", timeout=15
            )
            resp.raise_for_status()
            node_data = resp.json()
            node_id = node_data.get("id", "")
            if not node_id:
                return []

            # 获取节点帖子
            resp2 = self.session.get(
                f"{self.API_BASE}/topics/show.json?node_id={node_id}&p={page}",
                timeout=15
            )
            resp2.raise_for_status()
            topics = resp2.json()
        except Exception as e:
            print(f"[V2EX] 节点 {node_name} 失败: {e}")
            return []

        results = [self._format_topic(t) for t in topics[:20]]
        print(f"[V2EX] 节点 {node_name}: {len(results)} 帖")
        return results

    def fetch_all(self) -> list[dict]:
        """聚合：热门话题 + 重点 AI 节点"""
        all_results = []
        seen_urls = set()

        # 1. 热门话题（自动过滤 AI）
        for t in self.fetch_hot():
            url = t.get("url", "")
            if url not in seen_urls:
                all_results.append(t)
                seen_urls.add(url)

        # 2. 重点节点的最新帖子
        for node in ["ai", "programmer", "create"]:
            try:
                for r in self.fetch_node(node):
                    url = r.get("url", "")
                    if url not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(url)
            except Exception as e:
                print(f"[V2EX] 节点 {node} 跳过: {e}")

        print(f"[V2EX] 总计: {len(all_results)} 条")
        return all_results


# 独立运行测试
if __name__ == "__main__":
    scraper = V2EXScraper()
    topics = scraper.fetch_all()
    print(f"\n获取 {len(topics)} 条 AI 相关 V2EX 帖子")
    print("-" * 60)
    for t in topics[:10]:
        print(f"  💬{t['replies']:>3}  [{t.get('node',''):<10}] {t['title'][:55]}")
        print(f"         作者: {t.get('author','?')}  |  {t['url'][:60]}")
        print()
