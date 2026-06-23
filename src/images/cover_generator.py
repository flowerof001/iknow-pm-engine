"""封面图自动生成器 — 小红书风格信息卡片（需 Pillow）"""
import textwrap
from pathlib import Path
from typing import Optional

_HAS_PIL = False
try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:
    pass


class CoverGenerator:
    """生成岗位替代雷达、工具榜等栏目的封面信息图"""

    RISK_COLORS = {
        "high": "#E53E3E",
        "medium": "#DD6B20",
        "low": "#38A169",
        "bg": "#1A202C",
        "white": "#FFFFFF",
        "subtitle": "#A0AEC0",
        "accent": "#63B3ED",
    }

    SIZE_PORTRAIT = (1080, 1440)
    SIZE_WECHAT = (900, 383)

    def __init__(self, output_dir: Optional[Path] = None):
        from src.config import config
        self.output_dir = output_dir or config.OUTPUT_DIR / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _check_pil(self) -> bool:
        if not _HAS_PIL:
            print("[Cover] Pillow 未安装，跳过图片生成。安装: pip3 install Pillow")
            return False
        return True

    def _get_font(self, size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    def generate_risk_card(
        self,
        title: str,
        risk_signals: list[dict],
        date: str = "",
    ) -> Optional[Path]:
        """生成「岗位替代雷达」三色风险看板 (小红书版)"""
        if not self._check_pil():
            return None

        try:
            img = Image.new("RGB", self.SIZE_PORTRAIT, self.RISK_COLORS["bg"])
            draw = ImageDraw.Draw(img)

            y = 80
            title_font = self._get_font(56, bold=True)
            title_lines = textwrap.wrap(title, width=16)
            for line in title_lines:
                draw.text((80, y), line, fill=self.RISK_COLORS["white"], font=title_font)
                y += 72
            y += 30

            if date:
                date_font = self._get_font(28)
                draw.text((80, y), date, fill=self.RISK_COLORS["subtitle"], font=date_font)
                y += 50

            card_width = 920
            card_x = (self.SIZE_PORTRAIT[0] - card_width) // 2
            indicator_font = self._get_font(48)

            for signal in risk_signals[:6]:
                job = signal.get("job", "")
                level = signal.get("level", "🟡")
                change = signal.get("change", "")

                if "🔴" in level:
                    border_color = self.RISK_COLORS["high"]
                elif "🟡" in level:
                    border_color = self.RISK_COLORS["medium"]
                else:
                    border_color = self.RISK_COLORS["low"]

                draw.rounded_rectangle(
                    [card_x, y, card_x + card_width, y + 100],
                    radius=16, fill="#2D3748", outline=border_color, width=4,
                )
                draw.text((card_x + 30, y + 18), f"{level} {job}",
                         fill=self.RISK_COLORS["white"], font=indicator_font)

                if change:
                    change_color = self.RISK_COLORS["high"] if "-" in change else self.RISK_COLORS["low"]
                    bbox = draw.textbbox((0, 0), change, font=indicator_font)
                    tw = bbox[2] - bbox[0]
                    draw.text((card_x + card_width - tw - 30, y + 18), change,
                             fill=change_color, font=indicator_font)
                y += 120

            y = self.SIZE_PORTRAIT[1] - 160
            cta_font = self._get_font(28)
            draw.text((80, y), "关注公众号「AI职场竞争力引擎」",
                     fill=self.RISK_COLORS["accent"], font=cta_font)
            draw.text((80, y + 38), "每周获取你的岗位安全评估",
                     fill=self.RISK_COLORS["subtitle"], font=cta_font)

            filename = f"risk_card_{date.replace('-', '')}.png" if date else "risk_card.png"
            filepath = self.output_dir / filename
            img.save(filepath, "PNG", quality=95)
            print(f"[Cover] 已生成: {filepath}")
            return filepath

        except Exception as e:
            print(f"[Cover] 生成失败: {e}")
            return None

    def generate_tool_badge(
        self, tool_name: str, category: str, rating: int, one_liner: str,
    ) -> Optional[Path]:
        """生成「工具榜」封面图（公众号版）"""
        if not self._check_pil():
            return None

        try:
            img = Image.new("RGB", self.SIZE_WECHAT, self.RISK_COLORS["bg"])
            draw = ImageDraw.Draw(img)

            cat_font = self._get_font(24)
            cat_colors = {"PM": "#63B3ED", "Dev": "#68D391", "Ops": "#F6AD55"}
            cat_color = cat_colors.get(category, "#63B3ED")
            draw.rounded_rectangle([30, 30, 120, 60], radius=8, fill=cat_color)
            draw.text((50, 34), category, fill=self.RISK_COLORS["bg"], font=cat_font)

            name_font = self._get_font(48, bold=True)
            draw.text((30, 100), tool_name, fill=self.RISK_COLORS["white"], font=name_font)

            star_font = self._get_font(36)
            draw.text((30, 170), "⭐" * rating, fill="#F6E05E", font=star_font)

            desc_font = self._get_font(24)
            draw.text((30, 240), one_liner, fill=self.RISK_COLORS["subtitle"], font=desc_font)

            draw.rectangle([0, 370, self.SIZE_WECHAT[0], 383], fill=self.RISK_COLORS["accent"])

            filename = f"tool_{tool_name.replace(' ', '_')}.png"
            filepath = self.output_dir / filename
            img.save(filepath, "PNG", quality=95)
            print(f"[Cover] 已生成: {filepath}")
            return filepath

        except Exception as e:
            print(f"[Cover] 生成失败: {e}")
            return None
