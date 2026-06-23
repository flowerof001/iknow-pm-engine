"""模型解析器 — 根据业务类型从管理后台配置中解析模型参数"""
import json
import os
from pathlib import Path
from typing import Optional

# 自动加载 .env
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        with open(_env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

ADMIN_DIR = Path(__file__).parent.parent / "admin"
CONFIG_PATH = ADMIN_DIR / "model_config.json"
REGISTRY_PATH = ADMIN_DIR / "model_registry.json"


class ModelResolver:
    """读取 admin/model_config.json，按业务类型返回模型参数"""

    def __init__(self):
        self._config = None
        self._registry = None

    @property
    def config(self) -> dict:
        if self._config is None:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        return self._config

    @property
    def registry(self) -> dict:
        if self._registry is None:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                self._registry = json.load(f)
        return self._registry

    def resolve_text_model(self, language: str = "chinese") -> dict:
        """
        解析文本模型
        language: "chinese" → chinese_article, "english" → english_article
        返回: {model_key, api_type, base_url, model_id, api_key_env, ...}
        """
        biz_key = "chinese_article" if language == "chinese" else "english_article"
        return self._resolve("text_generation", biz_key, "text")

    def resolve_image_model(self, image_type: str = "realistic") -> dict:
        """
        解析图片模型
        image_type: "realistic" → english_realistic, 
                    "poster" → english_poster, 
                    "chinese" → chinese_image
        返回: {model_key, api_type, model_id, default_width, default_height, ...}
        """
        type_map = {
            "realistic": "english_realistic",
            "poster": "english_poster",
            "chinese": "chinese_image",
        }
        biz_key = type_map.get(image_type, "english_realistic")
        return self._resolve("image_generation", biz_key, "image")

    def _resolve(self, category: str, biz_key: str, model_category: str) -> dict:
        config = self.config
        registry = self.registry

        biz = config.get(category, {}).get(biz_key, {})
        model_key = biz.get("model_key", "")

        model_info = registry.get("models", {}).get(model_category, {}).get(model_key, {})
        if not model_info:
            # fallback to first available
            models = registry.get("models", {}).get(model_category, {})
            if models:
                model_key = list(models.keys())[0]
                model_info = models[model_key]

        return {
            "model_key": model_key,
            "business_type": biz_key,
            "category": category,
            **model_info,
        }

    def get_api_config(self, model_info: dict, api_key: str = "") -> dict:
        """从模型信息中提取 API 配置，自动读取 .env 中的 key"""
        env_key = model_info.get("api_key_env", "")
        resolved_key = api_key or os.getenv(env_key, "") or os.getenv("LLM_API_KEY", "")
        return {
            "api_key": resolved_key,
            "base_url": model_info.get("base_url", "https://api.openai.com/v1"),
            "model_id": model_info.get("model_id", model_info.get("model_key", "")),
        }

    def list_business_types(self) -> dict:
        """列出所有业务类型及其当前模型"""
        result = {}
        for category in ["text_generation", "image_generation"]:
            result[category] = {}
            for biz_key, biz in self.config.get(category, {}).items():
                result[category][biz_key] = {
                    "label": biz.get("label", biz_key),
                    "model": biz.get("model_key", ""),
                }
        return result


# 全局单例
resolver = ModelResolver()


# ── 便捷函数 ──

def get_text_model(language: str = "chinese") -> dict:
    """快捷获取文本模型配置"""
    return resolver.resolve_text_model(language)


def get_image_model(image_type: str = "realistic") -> dict:
    """快捷获取图片模型配置"""
    return resolver.resolve_image_model(image_type)


def print_current_config():
    """打印当前配置摘要（调试用）"""
    print("\n📋 当前模型配置:")
    print("-" * 50)
    for category, types in resolver.list_business_types().items():
        cat_name = "📝 文本生成" if category == "text_generation" else "🎨 图片生成"
        print(f"\n{cat_name}:")
        for key, info in types.items():
            print(f"  {info['label']:<20} → {info['model']}")


if __name__ == "__main__":
    print_current_config()

    print("\n🔍 解析示例:")
    text = resolver.resolve_text_model("chinese")
    print(f"  中文文章: {text['model_key']} @ {text.get('base_url', 'N/A')}")

    img = resolver.resolve_image_model("chinese")
    print(f"  中文图片: {img['model_key']} ({img.get('default_width', '?')}x{img.get('default_height', '?')})")
