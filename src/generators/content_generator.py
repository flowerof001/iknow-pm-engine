"""AI 内容生成器 — 调用 LLM API 生成各栏目内容"""
import json
from typing import Optional

from src.config import config
from src.model_resolver import resolver
from src.generators.pm_prompts import PM_PROMPTS as PROMPTS
from src.utils import retry, log


class ContentGenerator:
    """基于爬取的原始数据 + Prompt 模板，调用 LLM 生成结构化内容"""

    def __init__(self):
        self._client = None
        self.model = config.LLM_MODEL

    @property
    def client(self):
        """延迟加载 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                )
            except ImportError:
                raise RuntimeError(
                    "未安装 openai 包。请运行: pip3 install openai\n"
                    "或在 .env 中设置有效的 LLM_API_KEY"
                )
            except Exception as e:
                raise RuntimeError(f"OpenAI 客户端初始化失败: {e}")
        return self._client

    def _build_raw_data_text(self, data: list[dict], max_items: int = 30) -> str:
        """将爬取的原始数据拼成 LLM 可读的文本"""
        lines = []
        for i, item in enumerate(data[:max_items]):
            source = item.get("source", "unknown")
            title = item.get("title", "") or item.get("name", "")
            summary = item.get("summary", "") or item.get("description", "")
            url = item.get("url", "")
            stars = item.get("stars", "")
            published = item.get("published", "")
            categories = item.get("categories", [])

            parts = [f"### 条目 {i+1}"]
            parts.append(f"来源: {source}")
            parts.append(f"标题: {title}")
            if summary:
                parts.append(f"摘要: {summary}")
            if url:
                parts.append(f"链接: {url}")
            if stars:
                parts.append(f"星标: {stars}")
            if published:
                parts.append(f"日期: {published}")
            if categories:
                parts.append(f"分类: {', '.join(categories)}")
            lines.append("\n".join(parts))

        return "\n\n".join(lines)

    def generate_with_resolver(self, column: str, raw_data: list[dict],
                               language: str = "chinese",
                               max_tokens: int = 3000) -> Optional[str]:
        """使用管理后台配置的模型生成内容"""
        model_info = resolver.resolve_text_model(language)
        api_cfg = resolver.get_api_config(model_info, config.LLM_API_KEY)

        # 临时切换模型
        original_model = self.model
        self.model = api_cfg["model_id"]

        # 如果 base_url 不同，重建 client
        from openai import OpenAI
        original_client = self._client
        self._client = OpenAI(
            api_key=api_cfg["api_key"] or config.LLM_API_KEY,
            base_url=api_cfg["base_url"],
        )

        result = self.generate(column, raw_data, max_tokens)

        # 恢复
        self.model = original_model
        self._client = original_client

        return result

    @retry(max_attempts=3, base_delay=2.0, backoff=2.0)
    def _call_llm(self, system_prompt: str, user_prompt: str,
                  max_tokens: int = 3000) -> str:
        """调用 LLM（带指数退避重试，最多 3 次）"""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return resp.choices[0].message.content

    def generate(self, column: str, raw_data: list[dict],
                 max_tokens: int = 3000) -> Optional[str]:
        """
        生成单篇栏目内容
        column: 栏目 key（job_radar / job_compass / weekly_learn ...）
        raw_data: 爬取的原始数据列表
        """
        prompt_cfg = PROMPTS.get(column)
        if not prompt_cfg:
            log.warn("Generator", f"未知栏目: {column}")
            return None

        raw_text = self._build_raw_data_text(raw_data)
        if not raw_text.strip():
            log.warn("Generator", f"无可用数据，跳过 {column}")
            return None

        user_prompt = prompt_cfg["user"].format(raw_data=raw_text)

        try:
            return self._call_llm(prompt_cfg["system"], user_prompt, max_tokens)
        except Exception as e:
            log.error("Generator", f"LLM 调用最终失败 ({column}): {e}")
            return None

    def generate_batch(self, columns: list[str], raw_data: dict[str, list[dict]],
                       max_tokens: int = 3000) -> dict[str, Optional[str]]:
        """批量生成多个栏目（单栏目失败不影响其他）"""
        results = {}
        for col in columns:
            data = raw_data.get(col, [])
            if not data:
                log.warn("Generator", f"{col} 无数据，跳过")
                results[col] = None
                continue
            log.info("Generator", f"正在生成 {col} ...")
            try:
                results[col] = self.generate(col, data, max_tokens)
            except Exception as e:
                log.error("Generator", f"{col} 生成异常: {e}")
                results[col] = None
        return results

    # ── 便捷方法 ──
    def job_radar(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("job_radar", raw_data)

    def job_compass(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("job_compass", raw_data)

    def weekly_learn(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("weekly_learn", raw_data)

    def tool_ranking(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("tool_ranking", raw_data)

    def case_study(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("case_study", raw_data)

    def hiring_signals(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("hiring_signals", raw_data)

    def salary_report(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("salary_report", raw_data, max_tokens=4000)

    def template_lib(self, raw_data: list[dict]) -> Optional[str]:
        return self.generate("template_lib", raw_data)
