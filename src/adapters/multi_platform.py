"""多平台版本改写 — 一篇长文 → 公众号 / 即刻 / 小红书 / 知乎 / 脉脉 / 微信群"""
import re
from typing import Optional
from src.config import config

ADAPT_SYSTEM = """你是一位资深社交媒体运营，擅长把同一篇长内容改写成不同平台的版本。
你的核心原则：
- 保留原文核心信息和数据点
- 适配各平台语言风格和字数限制
- 改写后可直接复制粘贴发布，不需要二次加工
- 标题和开头要有钩子，吸引点击/互动"""

ADAPT_PROMPT = """请将以下文章改写成 6 个平台版本：

<原文>
{article}
</原文>

⚠️ 严格按照以下格式输出，每个版本用 `---` 分隔：

### 公众号版
（1200-2500 字，保留原文核心结构，适合微信阅读的排版风格，加适当小标题和视觉分隔）

---
### 即刻版
（150-400 字，口语化，带讨论感，末尾加一个互动问题引导评论区讨论。不写"大家好"，直接说事。）

---
### 小红书版
（80-200 字，情绪化表达，加 emoji，用感叹号和反问句增加感染力。适合信息图配文。末尾加 3-5 个相关话题标签）

---
### 知乎版
（600-1500 字，偏专业的深度分析，有论点有论据，适合作为某热门话题的回答。开头引用一个典型场景或问题）

---
### 脉脉版
（100-250 字，职场视角，制造适度焦虑但给解决方案。适合在 #AI #职场 话题下发帖。末尾加一个投票式互动）

---
### 微信群转发版
（60-200 字，精华摘要，点到为止。末尾加「全文见公众号」引导）

只输出以上内容，不要额外解释。"""


class MultiPlatformAdapter:
    """将长文章改写为 6 个平台版本"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                )
            except ImportError:
                raise RuntimeError("未安装 openai 包: pip3 install openai")
        return self._client

    def adapt(self, article: str, max_tokens: int = 4000) -> Optional[dict[str, str]]:
        """输入一篇长文，返回 6 个平台版本"""
        prompt = ADAPT_PROMPT.format(article=article)

        try:
            resp = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": ADAPT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.8,
            )
            raw = resp.choices[0].message.content or ""
            return self._parse(raw)
        except Exception as e:
            print(f"[Adapter] LLM 调用失败: {e}")
            return None

    def _parse(self, raw: str) -> dict[str, str]:
        """解析 LLM 返回的 6 平台版本"""
        platforms = {
            "wechat": "", "jike": "", "xiaohongshu": "",
            "zhihu": "", "maimai": "", "wechat_group": "",
        }

        sections = re.split(r'\n(?=### )', raw)
        name_map = {
            "公众号": "wechat", "即刻": "jike", "小红书": "xiaohongshu",
            "知乎": "zhihu", "脉脉": "maimai", "微信群": "wechat_group",
            "微信": "wechat_group",
        }

        for section in sections:
            section = section.strip()
            for cn_name, key in name_map.items():
                if section.startswith(f"### {cn_name}"):
                    content = re.sub(r'^### .*?\n', '', section)
                    content = content.replace("\n---", "").strip()
                    platforms[key] = content
                    break

        return platforms

    
    def adapt_single(self, column: str, article: str) -> dict[str, str]:
        """单篇文章多平台改写（简化接口，不调用 LLM）"""
        versions = self.adapt(article)
        return versions or {}
    
    def format_multi_platform(self, column: str, article: str, versions: dict[str, str]) -> str:
        """格式化多平台版本为 Markdown"""
        lines = [article, "", "---", "", "## 📱 多平台版本", ""]
        platform_names = {
            "wechat": "📱 公众号长文",
            "jike": "🟡 即刻版",
            "xiaohongshu": "📕 小红书版",
            "zhihu": "📚 知乎版",
            "maimai": "💼 脉脉版",
            "wechat_group": "💬 微信群版",
        }
        for key, name in platform_names.items():
            if key in versions:
                lines.append(f"### {name}")
                lines.append("")
                lines.append(versions[key])
                lines.append("")
        return "\n".join(lines)

    def adapt_to_text(self, article: str) -> Optional[str]:
        """返回原始文本（方便存文件）"""
        versions = self.adapt(article)
        if not versions:
            return None

        lines = []
        labels = {
            "wechat": "📱 公众号版", "jike": "🟡 即刻版",
            "xiaohongshu": "📕 小红书版", "zhihu": "📚 知乎版",
            "maimai": "💼 脉脉版", "wechat_group": "💬 微信群版",
        }

        for key, label in labels.items():
            content = versions.get(key, "")
            if content:
                lines.append(f"## {label}\n\n{content}\n")
                lines.append("---\n")

        return "\n".join(lines)
