"""FLUX.1-dev 文生图模块 — 通过 Replicate API 生成 16:9 横版图片"""
import time
import requests
from pathlib import Path
from typing import Optional
from src.config import config
from src.model_resolver import resolver


class FluxGenerator:
    """基于文章主题，用 FLUX.1-dev 生成 16:9 配图"""

    # 16:9 2K 分辨率
    WIDTH = 1920
    HEIGHT = 1080

    # FLUX 1K 预览尺寸
    PREVIEW_WIDTH = 1280
    PREVIEW_HEIGHT = 720

    # FLUX.1-dev 在 Replicate 上的模型标识
    MODEL = "black-forest-labs/flux-dev"  # 默认值，会被 model_resolver 覆盖

    def __init__(self, replicate_token: Optional[str] = None):
        self.token = replicate_token or config.REPLICATE_API_TOKEN
        self.output_dir = config.OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._has_pil = False
        try:
            from PIL import Image
            self._has_pil = True
        except ImportError:
            pass

    def _build_prompt(self, article: str) -> str:
        """从文章提取图片生成 prompt（英文，FLUX 英文效果更好）"""
        # 取标题 + 前 300 字作为 prompt 素材
        lines = article.strip().split("\n")
        title = ""
        body = ""

        for line in lines:
            line = line.strip()
            if not title and ("标题" in line or "预警" in line or line.startswith("##") or line.startswith("**")):
                title = line.lstrip("#* ").strip()
            elif not title and len(line) > 10:
                title = line[:100]

        body = " ".join(lines[:15])[:400]

        # 用 LLM 翻译 + 优化为英文图片 prompt
        prompt = (
            f"Translate the following Chinese article theme into a concise English image generation prompt "
            f"(under 60 words) for FLUX.1-dev. The image should be a professional, modern illustration "
            f"suitable for a tech career blog, with a clean composition and cinematic lighting. "
            f"Use descriptive visual language, no text in the image.\n\n"
            f"Title: {title}\nTheme: {body[:200]}"
        )
        return prompt

    def _optimize_prompt_with_llm(self, article: str) -> str:
        """用 LLM 将中文主题转为 FLUX 优化 prompt"""
        from openai import OpenAI

        client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
        )

        # 提取文章主题
        lines = article.strip().split("\n")
        title = ""
        for line in lines:
            line = line.strip().lstrip("#* ")
            if len(line) > 8 and ("预警" in line or "替代" in line or "岗位" in line or "AI" in line):
                title = line[:120]
                break
        if not title:
            title = lines[0][:120] if lines else "AI career trend visualization"

        body_snippet = " ".join(lines[:10])[:300]

        try:
            resp = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{
                    "role": "user",
                    "content": (
                        "You are a prompt engineer for FLUX.1-dev image generation. "
                        "Convert this Chinese article theme into an English image prompt.\n\n"
                        "Rules:\n"
                        "- Under 60 words\n"
                        "- Describe a professional, modern illustration for a tech career blog\n"
                        "- Clean composition, cinematic lighting, 16:9 aspect ratio\n"
                        "- NO text/letters/numbers in the image\n"
                        "- Use descriptive visual language\n\n"
                        f"Chinese title: {title}\n"
                        f"Context: {body_snippet}\n\n"
                        "English prompt:"
                    ),
                }],
                max_tokens=120,
                temperature=0.7,
            )
            prompt = resp.choices[0].message.content.strip().strip('"')
            print(f"[Flux] 图片 Prompt: {prompt[:100]}...")
            return prompt
        except Exception as e:
            print(f"[Flux] Prompt 优化失败: {e}, 使用备用 prompt")
            return f"Futuristic illustration representing {title[:60]}, professional tech aesthetic, cinematic lighting, 16:9"

    def generate(self, article: str, date_str: str = "", image_type: str = "realistic",
                 width: int = WIDTH, height: int = HEIGHT) -> Optional[dict]:
        """
        生成 16:9 图片
        返回: {"2k": Path, "1k": Path} 或 None
        """
        if not self.token:
            print("[Flux] 未配置 REPLICATE_API_TOKEN，跳过图片生成")
            return None

        # Step 1: 生成优化 prompt
        prompt = self._optimize_prompt_with_llm(article)

        # Step 2: 根据业务类型解析模型
        try:
            img_model = resolver.resolve_image_model(image_type)
            model_id = img_model.get("model_id", self.MODEL)
            width = img_model.get("default_width", width)
            height = img_model.get("default_height", height)
            print(f"[Flux] 使用模型: {model_id} ({img_model.get("vendor","?")})")
        except Exception:
            model_id = self.MODEL
            print(f"[Flux] model_resolver 不可用，使用默认: {model_id}")

        # Step 3: 调用 Replicate API
        print(f"[Flux] 调用 {model_id} 生成 {width}x{height} ...")
        image_url = self._call_replicate(prompt, width, height, model=model_id)
        if not image_url:
            return None

        # Step 4: 下载原图 (2K)
        date_prefix = date_str.replace("-", "") if date_str else "output"
        filename_2k = f"{date_prefix}_flux_2k.png"
        filepath_2k = self.output_dir / filename_2k

        print(f"[Flux] 下载原图 ...")
        if not self._download_image(image_url, filepath_2k):
            return None

        # Step 5: 缩放到 1K
        filename_1k = f"{date_prefix}_flux_1k.png"
        filepath_1k = self.output_dir / filename_1k

        if self._has_pil:
            from PIL import Image
            img = Image.open(filepath_2k)
            img_1k = img.resize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT), Image.LANCZOS)
            img_1k.save(filepath_1k, "PNG", quality=90)
            print(f"[Flux] 已缩放至 1K: {filepath_1k}")
        else:
            # 无 Pillow，复制原图
            import shutil
            shutil.copy(filepath_2k, filepath_1k)
            print(f"[Flux] Pillow 未安装，1K=2K: {filepath_1k}")

        return {"2k": filepath_2k, "1k": filepath_1k}

    def _call_replicate(self, prompt: str, width: int, height: int, model: str = None,
                        num_outputs: int = 1, timeout: int = 120) -> Optional[str]:
        """调用 Replicate API 生成图片"""
        try:
            # Step 1: 创建预测
            resp = requests.post(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-dev/predictions",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": {
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                        "num_outputs": num_outputs,
                        "aspect_ratio": "16:9",
                        "output_format": "png",
                        "output_quality": 90,
                        "num_inference_steps": 28,
                        "guidance_scale": 3.5,
                    }
                },
                timeout=30,
            )
            resp.raise_for_status()
            prediction = resp.json()
        except Exception as e:
            print(f"[Flux] Replicate 请求失败: {e}")
            return None

        # Step 2: 轮询等待完成
        poll_url = prediction.get("urls", {}).get("get", "")
        if not poll_url:
            # 兼容不同 Replicate API 版本
            pred_id = prediction.get("id", "")
            if pred_id:
                poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"
            else:
                print("[Flux] 无法获取预测 URL")
                return None

        print(f"[Flux] 等待生成完成 ...")
        for attempt in range(timeout):
            time.sleep(2)
            try:
                resp = requests.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=10,
                )
                resp.raise_for_status()
                status_data = resp.json()

                status = status_data.get("status", "")
                if status == "succeeded":
                    output = status_data.get("output", [])
                    image_url = output[0] if isinstance(output, list) else output
                    print(f"[Flux] ✅ 生成完成")
                    return image_url
                elif status == "failed":
                    print(f"[Flux] ❌ 生成失败: {status_data.get('error', 'unknown')}")
                    return None
                elif status == "canceled":
                    print(f"[Flux] ⚠️ 生成被取消")
                    return None
                else:
                    # processing / starting
                    if attempt % 5 == 0:
                        print(f"[Flux] 状态: {status} ({attempt * 2}s)")
            except Exception as e:
                print(f"[Flux] 轮询异常: {e}")

        print(f"[Flux] ⏰ 超时 ({timeout}s)")
        return None

    def _download_image(self, url: str, filepath: Path) -> bool:
        """下载图片到本地"""
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)
            print(f"[Flux] 已保存: {filepath} ({len(resp.content) // 1024} KB)")
            return True
        except Exception as e:
            print(f"[Flux] 下载失败: {e}")
            return False

    def embed_image_in_article(self, article: str, image_path_1k: Path, 
                               image_path_2k: Optional[Path] = None) -> str:
        """在文章开头插入 1K 图片的 Markdown 引用"""
        rel_path_1k = image_path_1k.name

        img_md = (
            f"![配图]({rel_path_1k})\n\n"
            f"> *AI 生成配图 · 点击查看 [2K 高清版]({image_path_2k.name if image_path_2k else rel_path_1k})*\n\n"
            "---\n\n"
        )
        return img_md + article


# ── 简化版：不用 API，直接调 Replicate 的便捷函数 ──

def generate_article_cover(article: str, config=None) -> Optional[dict]:
    """便捷函数"""
    gen = FluxGenerator()
    return gen.generate(article)
