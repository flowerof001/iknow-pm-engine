"""主流水线 — 串联爬虫 → 生成 → 适配 → 输出"""
import sys
import json
from datetime import datetime
from pathlib import Path

# 确保项目根在 path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import config
from src.scrapers.github_scraper import GitHubScraper
from src.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.news_scraper import NewsScraper
from src.scrapers.hn_scraper import HNScraper
from src.scrapers.juejin_scraper import JuejinScraper
from src.scrapers.v2ex_scraper import V2EXScraper
from src.generators.content_generator import ContentGenerator
from src.adapters.multi_platform import MultiPlatformAdapter
from src.images.cover_generator import CoverGenerator
from src.images.flux_generator import FluxGenerator
from src.utils import log


class Pipeline:
    """AI 职场竞争力引擎 — 完整内容流水线"""

    def __init__(self):
        self.github = GitHubScraper()
        self.arxiv = ArxivScraper()
        self.news = NewsScraper()
        self.hn = HNScraper()
        self.juejin = JuejinScraper()
        self.v2ex = V2EXScraper()
        self.generator = ContentGenerator()
        self.adapter = MultiPlatformAdapter()
        self.cover = CoverGenerator()
        self.flux = FluxGenerator()

        today = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = config.OUTPUT_DIR / today
        self.today_dir.mkdir(parents=True, exist_ok=True)

    # ─── Step 1: 采集 ─────────────────────────────────

    def collect_all(self) -> dict:
        """运行全部爬虫，返回分源原始数据（单个 scraper 失败不影响其他）"""
        log.info("Pipeline", "Step 1: 信息采集")

        raw = {}
        scrapers = [
            ("github", "GitHub Trending", lambda: self.github.fetch(days_back=3)),
            ("arxiv", "arXiv AI 论文", lambda: self.arxiv.fetch(max_results=20)),
            ("news", "AI 行业新闻", lambda: self.news.fetch_all()),
            ("hackernews", "Hacker News", lambda: self.hn.fetch(max_items=30)),
            ("juejin", "掘金 AI 文章", lambda: self.juejin.fetch(limit=20)),
            ("v2ex", "V2EX AI 热帖", lambda: self.v2ex.fetch_all()),
        ]

        for i, (key, label, fetch_fn) in enumerate(scrapers, 1):
            try:
                log.info("Pipeline", f"[{i}/{len(scrapers)}] {label} ...")
                raw[key] = fetch_fn()
            except Exception as e:
                log.error("Pipeline", f"{label} 采集失败: {e}")
                raw[key] = []

        # 统计
        for source, items in raw.items():
            status = f"{len(items)} 条" if items else "空"
            log.info("Pipeline", f"  {source}: {status}")

        # 保存原始数据
        raw_path = self.today_dir / "raw_data.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2, default=str)

        log.info("Pipeline", f"原始数据已保存: {raw_path}")
        return raw

    # ─── Step 2: 路由数据到各栏目 ──────────────────────

    def route_data(self, raw: dict) -> dict[str, list]:
        """将原始数据按栏目需求分配"""
        log.info("Pipeline", "Step 2: 数据路由")

        github = raw.get("github", [])
        arxiv = raw.get("arxiv", [])
        news = raw.get("news", [])
        hn = raw.get("hackernews", [])
        juejin = raw.get("juejin", [])
        v2ex = raw.get("v2ex", [])

        # 合并全部数据（用于通用栏目）
        all_items = github + arxiv + news + hn + juejin + v2ex

        routed = {
            # Phase 1 栏目：免费引流
            "job_radar": all_items,              # 招聘+技术+新闻综合
            "job_compass": all_items,             # 招聘+技术趋势
            "weekly_learn": github + arxiv + hn + juejin,  # GitHub + 论文 + HN + 掘金

            # Phase 2 栏目：付费墙
            "tool_ranking": github + hn + juejin,        # GitHub 新项目 + HN 发布 + 掘金测评
            "case_study": news + juejin,                  # 行业新闻案例 + 掘金实践
            "template_lib": github + arxiv + juejin,     # 新工具→新模板
            "hiring_signals": all_items,                  # 综合信息源
        }

        for col, items in routed.items():
            log.info("Pipeline", f"  {col}: {len(items)} 条数据")

        return routed

    # ─── Step 3: AI 生成 ───────────────────────────────

    def generate_content(self, routed: dict, columns: list[str]) -> dict:
        """调用 LLM 生成指定栏目内容（单栏目失败不影响其他）"""
        log.info("Pipeline", "Step 3: AI 内容生成")

        results = {}
        for col in columns:
            data = routed.get(col, [])
            if not data:
                log.warn("Pipeline", f"  {col}: 无数据，跳过")
                results[col] = None
                continue

            try:
                log.info("Pipeline", f"  ✍️  生成 {col} ...")
                content = self.generator.generate(col, data)
                results[col] = content

                if content:
                    filename = config.OUTPUT_FILES.get(col, f"{col}_{{date}}.md")
                    filename = filename.format(date=datetime.now().strftime("%Y%m%d"))
                    filepath = self.today_dir / filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    log.info("Pipeline", f"  ✅ {col}: {len(content)} 字 → {filename}")
                else:
                    log.warn("Pipeline", f"  ❌ {col}: 生成返回空")
            except Exception as e:
                log.error("Pipeline", f"  ❌ {col}: 生成异常 - {e}")
                results[col] = None

        return results

    # ─── Step 4: 多平台改写 ────────────────────────────

    def adapt_content(self, generated: dict) -> dict:
        """将生成的文章改写为多平台版本（单篇失败不影响其他）"""
        log.info("Pipeline", "Step 4: 多平台改写")

        all_versions = {}

        for col, article in generated.items():
            if not article:
                continue

            try:
                log.info("Pipeline", f"  📝 {col} → 6 平台 ...")
                versions = self.adapter.adapt_to_text(article)

                if versions:
                    all_versions[col] = versions
                    filename = f"{datetime.now().strftime('%Y%m%d')}_{col}_多平台版.md"
                    filepath = self.today_dir / filename
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(versions)
                    log.info("Pipeline", f"  ✅ 已保存: {filename}")
                else:
                    log.warn("Pipeline", f"  ⚠️  {col}: 改写返回空")
            except Exception as e:
                log.error("Pipeline", f"  ⚠️  {col}: 改写异常 - {e}")

        return all_versions

    # ─── Step 5: 生成每日发布面板 ──────────────────────

    def generate_publish_panel(self, generated: dict, all_versions: dict):
        """生成一个汇总 Markdown — 每日看一眼就可以发布的操控面板"""
        log.info("Pipeline", "Step 5: 生成发布面板")

        lines = [
            f"# 📋 AI 职场竞争力引擎 — 每日发布面板",
            f"**日期：** {datetime.now().strftime('%Y-%m-%d %A')}",
            "",
            "> 👇 以下内容可直接复制粘贴到各平台发布",
            "",
            "---",
            "",
            "## 📱 公众号主推（选择 1 篇）",
            "",
        ]

        # 公众号版本（从第一个有内容的栏目取多平台版）
        for col in ["job_radar", "weekly_learn", "job_compass"]:
            article = generated.get(col)
            if article:
                lines.append(f"### 推荐：{col}")
                lines.append("")
                lines.append("**完整长文：**")
                lines.append("")
                lines.append(article)
                lines.append("")
                lines.append("---")
                break

        # 即刻 / 脉脉 / 微信群 短版
        lines.append("")
        lines.append("## 🟡 即刻 / 💼 脉脉 / 💬 微信群 短版")
        lines.append("")
        lines.append("> 以下为精简版，适配即刻、脉脉、微信群转发")
        lines.append("")

        for col, text in all_versions.items():
            # 提取微信群版（取第一个 ### 之后的短版内容）
            if "微信群" in text or "💬" in text:
                lines.append(f"### {col}")
                lines.append(text)
                lines.append("")
                break

        lines.append("---")
        lines.append("")
        lines.append("## 📊 今日数据统计")
        lines.append("")

        # 统计
        for col, article in generated.items():
            status = "✅" if article else "❌"
            word_count = len(article) if article else 0
            lines.append(f"- {status} **{col}**: {word_count} 字")

        lines.append("")
        lines.append("## 🎨 生成图片")
        # 列出已生成的图片
        img_dir = self.today_dir.parent / "images"
        if img_dir.exists():
            for img in sorted(img_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                lines.append(f"- ![]({img})")

        lines.append("")
        lines.append("---")
        lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        panel = "\n".join(lines)
        panel_path = self.today_dir / f"{datetime.now().strftime('%Y%m%d')}_发布面板.md"
        with open(panel_path, "w", encoding="utf-8") as f:
            f.write(panel)

        print(f"        📋 已生成: {panel_path}")
        return panel_path

    # ─── 入口 ──────────────────────────────────────────


    # ─── Step 3.5: FLUX 封面图 ─────────────────────────

    def generate_cover_image(self, generated: dict) -> Optional[dict]:
        """为主推文章生成 FLUX 16:9 配图"""
        log.info("Pipeline", "Step 3.5: FLUX 封面图生成")

        # 取第一篇文章（job_radar 优先）
        for col in ["job_radar", "weekly_learn", "job_compass"]:
            article = generated.get(col)
            if article:
                print(f"        为 {col} 生成配图 ...")
                result = self.flux.generate(article)
                if result:
                    # 将 1K 图嵌入文章
                    updated = self.flux.embed_image_in_article(
                        article, result["1k"], result["2k"]
                    )
                    generated[col] = updated
                    print(f"        ✅ 配图已嵌入 {col}")
                else:
                    print(f"        ⚠️  图片生成跳过（无 API token 或失败）")
                return result
        return None


    def run(self, columns: list[str] = None, skip_scrape: bool = False):
        """
        运行完整流水线
        columns: 要生成的栏目列表，默认 Phase 1 三栏
        skip_scrape: 跳过爬虫（使用已有 raw_data.json）
        """
        if columns is None:
            # 默认 Phase 1 栏目
            columns = ["job_radar", "job_compass", "weekly_learn"]

        print("\n" + "🚀" * 30)
        print("  AI 职场竞争力引擎 — 内容流水线启动")
        print("🚀" * 30)

        # Step 1: 采集
        if skip_scrape:
            raw_path = self.today_dir / "raw_data.json"
            if raw_path.exists():
                with open(raw_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                print(f"\n  📂 使用已有数据: {raw_path}")
            else:
                print(f"\n  ❌ 未找到已有数据，自动采集 ...")
                raw = self.collect_all()
        else:
            raw = self.collect_all()

        # Step 2: 路由
        routed = self.route_data(raw)

        # Step 3: 生成
        generated = self.generate_content(routed, columns)

        # Step 3.5: FLUX 图片生成
        image_paths = self.generate_cover_image(generated)

        # Step 4: 多平台改写
        all_versions = self.adapt_content(generated)

        # Step 5: 发布面板
        panel_path = self.generate_publish_panel(generated, all_versions)

        # 可选：生成封面图
        # self.cover.generate_risk_card(...)

        print("\n" + "="*60)
        print(f"  ✅ 流水线完成！")
        print(f"  📂 输出目录: {self.today_dir}")
        print(f"  📋 发布面板: {panel_path}")
        print("="*60 + "\n")

        return {
            "raw": raw,
            "routed": routed,
            "generated": generated,
            "all_versions": all_versions,
            "panel_path": panel_path,
        }


# ── CLI 入口 ──────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI 职场竞争力引擎 — 内容流水线")
    parser.add_argument(
        "--columns", "-c", nargs="+",
        default=["job_radar", "job_compass", "weekly_learn"],
        help="要生成的栏目（默认: job_radar job_compass weekly_learn）"
    )
    parser.add_argument(
        "--skip-scrape", "-s", action="store_true",
        help="跳过爬虫，使用已有 raw_data.json"
    )
    parser.add_argument(
        "--all", "-a", action="store_true",
        help="生成全部 8 个栏目"
    )

    args = parser.parse_args()

    if args.all:
        args.columns = [
            "job_radar", "job_compass", "weekly_learn",
            "tool_ranking", "case_study", "template_lib",
            "hiring_signals",
        ]

    pipeline = Pipeline()
    result = pipeline.run(columns=args.columns, skip_scrape=args.skip_scrape)
