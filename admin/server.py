"""iKnow — AI 产品经理内容引擎 管理后台"""
import json
import sys
import asyncio
import queue
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 项目根
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from admin.data import (
    get_db, create_run, update_run, get_runs, get_run,
    save_content, get_contents, get_content, update_content,
    get_dates_with_content, get_stats, save_raw_data,
    get_source_status, update_source_status
)

ADMIN_DIR = Path(__file__).parent
REGISTRY_PATH = ADMIN_DIR / "model_registry.json"
CONFIG_PATH = ADMIN_DIR / "model_config.json"

app = FastAPI(title="iKnow - AI PM 内容引擎", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(ADMIN_DIR / "static")), name="static")


# ── SSE 进度推送 ──────────────────────────────────
pipeline_queues: dict[int, queue.Queue] = {}

def _publish_progress(run_id: int, msg: str, step: str = "", pct: int = 0):
    """向 SSE 队列推送进度"""
    q = pipeline_queues.get(run_id)
    if q:
        q.put(json.dumps({"msg": msg, "step": step, "pct": pct}, ensure_ascii=False))


# ── JSON 工具 ─────────────────────────────────────
def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: Path, data: dict):
    data["_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════
#  首页
# ═══════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = ADMIN_DIR / "static" / "index.html"
    return html_path.read_text(encoding="utf-8") if html_path.exists() else "<h1>iKnow</h1>"


@app.get("/health")
def health():
    return {"status": "ok", "name": "iKnow", "timestamp": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════
#  仪表盘 API
# ═══════════════════════════════════════════════════

@app.get("/api/stats")
def api_stats():
    stats = get_stats()
    sources = get_source_status()
    return {**stats, "sources": sources}


@app.get("/api/sources/status")
def api_source_status():
    return get_source_status()


@app.post("/api/sources/test/{source}")
def api_test_source(source: str):
    """测试单个数据源"""
    results = []
    try:
        if source == "woshipm":
            from src.scrapers.woshipm_scraper import WoshipmScraper
            s = WoshipmScraper()
            items = s.fetch(5)
            results = items[:3]
        elif source == "github":
            from src.scrapers.github_scraper import GitHubScraper
            s = GitHubScraper()
            items = s.fetch(days_back=3)
            results = items[:3]
        elif source == "arxiv":
            from src.scrapers.arxiv_scraper import ArxivScraper
            s = ArxivScraper()
            items = s.fetch(max_results=5)
            results = items[:3]
        elif source == "news":
            from src.scrapers.news_scraper import NewsScraper
            s = NewsScraper()
            items = s.fetch_all()
            results = items[:3]
        elif source == "hackernews":
            from src.scrapers.hn_scraper import HNScraper
            s = HNScraper()
            items = s.fetch(max_items=5)
            results = items[:3]
        elif source == "juejin":
            from src.scrapers.juejin_scraper import JuejinScraper
            s = JuejinScraper()
            items = s.fetch(limit=5)
            results = items[:3]
        elif source == "v2ex":
            from src.scrapers.v2ex_scraper import V2EXScraper
            s = V2EXScraper()
            items = s.fetch_hot()
            results = items[:3]
        else:
            return {"status": "error", "msg": f"未知数据源: {source}"}

        update_source_status(source, "ok" if results else "empty", "" if results else "无数据")
        return {"status": "ok", "count": len(results), "sample": results}
    except Exception as e:
        update_source_status(source, "error", str(e))
        return {"status": "error", "msg": str(e)}


# ═══════════════════════════════════════════════════
#  流水线 API
# ═══════════════════════════════════════════════════

class PipelineRunRequest(BaseModel):
    columns: list[str] = ["ai_product_radar", "ai_product_signal", "pm_toolbox",
                          "ai_product_deepdive", "pm_practice_notes"]
    skip_scrape: bool = False
    generate_images: bool = False


@app.post("/api/pipeline/run")
def api_pipeline_run(req: PipelineRunRequest):
    """启动流水线（后台异步执行，SSE 推送进度）"""
    run_id = create_run(req.columns)
    pipeline_queues[run_id] = queue.Queue()

    # 后台异步执行
    import threading
    def _run():
        try:
            _publish_progress(run_id, "🚀 流水线启动", "init", 0)
            result = _execute_pipeline(run_id, req.columns, req.skip_scrape, req.generate_images)
            update_run(run_id, "completed", 
                       output_dir=str(result.get("panel_path", "")),
                       sources_summary={k: len(v) for k, v in result.get("raw", {}).items()})
            _publish_progress(run_id, "✅ 流水线完成", "done", 100)
        except Exception as e:
            import traceback
            update_run(run_id, "failed", error=traceback.format_exc())
            _publish_progress(run_id, f"❌ 失败: {e}", "error", 0)
        finally:
            # 5 秒后清理队列
            def _clean():
                import time
                time.sleep(5)
                pipeline_queues.pop(run_id, None)
            threading.Thread(target=_clean).start()

    threading.Thread(target=_run, daemon=True).start()
    return {"run_id": run_id, "status": "started"}


def _execute_pipeline(run_id: int, columns: list[str], skip_scrape: bool, 
                      generate_images: bool) -> dict:
    """实际执行流水线"""
    from src.config import config
    from src.scrapers.github_scraper import GitHubScraper
    from src.scrapers.arxiv_scraper import ArxivScraper
    from src.scrapers.news_scraper import NewsScraper
    from src.scrapers.hn_scraper import HNScraper
    from src.scrapers.juejin_scraper import JuejinScraper
    from src.scrapers.v2ex_scraper import V2EXScraper
    from src.scrapers.woshipm_scraper import WoshipmScraper
    from src.generators.pm_prompts import PM_PROMPTS
    from src.generators.content_generator import ContentGenerator
    from src.adapters.multi_platform import MultiPlatformAdapter

    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = config.OUTPUT_DIR / today
    today_dir.mkdir(parents=True, exist_ok=True)

    raw = {}

    # Step 1: 采集
    _publish_progress(run_id, "📡 开始采集数据...", "scrape", 5)

    if skip_scrape:
        raw_path = today_dir / "raw_data.json"
        if raw_path.exists():
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _publish_progress(run_id, "📂 使用已有数据", "scrape", 15)
    else:
        scrapers = [
            ("woshipm", WoshipmScraper(), "fetch", [15]),
            ("github", GitHubScraper(), "fetch", [3]),
            ("arxiv", ArxivScraper(), "fetch", [15]),
            ("hackernews", HNScraper(), "fetch", [30]),
            ("juejin", JuejinScraper(), "fetch", [20]),
            ("v2ex", V2EXScraper(), "fetch_all", []),
            ("news", NewsScraper(), "fetch_all", []),
        ]
        for i, (name, scraper, method, args) in enumerate(scrapers):
            _publish_progress(run_id, f"📡 采集 {name} ...", "scrape", 10 + i * 10)
            try:
                fn = getattr(scraper, method)
                items = fn(*args)
                raw[name] = items
                save_raw_data(run_id, name, items, len(items))
                update_source_status(name, "ok", "" if items else "无数据")
            except Exception as e:
                raw[name] = []
                update_source_status(name, "error", str(e))

    # 保存原始数据
    raw_path = today_dir / "raw_data.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2, default=str)

    # Step 2: 路由
    _publish_progress(run_id, "🔀 数据路由...", "route", 55)
    all_items = []
    for source_items in raw.values():
        all_items.extend(source_items)
    
    # PM 专栏侧重
    woshipm = raw.get("woshipm", [])
    github = raw.get("github", [])
    juejin = raw.get("juejin", [])
    v2ex = raw.get("v2ex", [])
    hn = raw.get("hackernews", [])
    
    routed = {
        "ai_product_radar": all_items,
        "ai_product_signal": woshipm + hn + juejin + v2ex,
        "pm_toolbox": juejin + github + woshipm,
        "ai_product_deepdive": woshipm + hn + juejin,
        "pm_practice_notes": woshipm + juejin + v2ex,
    }

    # Step 3: 生成
    _publish_progress(run_id, "🤖 AI 内容生成中...", "generate", 60)
    generator = ContentGenerator()
    adapter = MultiPlatformAdapter()
    generated = {}

    for i, col in enumerate(columns):
        if col not in PM_PROMPTS:
            continue
        data = routed.get(col, [])
        if not data:
            data = all_items[:10]
        
        pct = 60 + (i + 1) * 7
        _publish_progress(run_id, f"✍️ 生成 {col} ...", "generate", pct)
        
        try:
            content = generator.generate(col, data, max_tokens=3000)
            if not content:
                continue
            
            # 提取标题
            lines = content.strip().split("\n")
            title = ""
            for line in lines:
                line = line.strip()
                if line.startswith("## ") or line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break
            if not title:
                title = lines[0].strip() if lines else col

            # 多平台改写
            _publish_progress(run_id, f"🔄 多平台改写 {col} ...", "adapt", pct + 3)
            versions = adapter.adapt_single(col, content)
            
            generated[col] = content
            
            # 保存到数据库
            save_content(
                run_id=run_id,
                column_key=col,
                title=title,
                content=content,
                platform_versions=versions,
                word_count=len(content),
                date=today,
            )
            
            # 保存文件
            filename = f"{today.replace('-', '')}_{col}.md"
            filepath = today_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 多平台版本文件
            mp_filename = f"{today.replace('-', '')}_{col}_多平台版.md"
            mp_filepath = today_dir / mp_filename
            with open(mp_filepath, "w", encoding="utf-8") as f:
                f.write(adapter.format_multi_platform(col, content, versions))

        except Exception as e:
            _publish_progress(run_id, f"⚠️ {col} 生成失败: {e}", "generate", pct)

    _publish_progress(run_id, "✅ 内容生成完成", "done", 95)
    return {"raw": raw, "routed": routed, "generated": generated, 
            "panel_path": str(today_dir)}


@app.get("/api/pipeline/stream/{run_id}")
async def api_pipeline_stream(run_id: int):
    """SSE 实时推送流水线进度"""
    q = pipeline_queues.get(run_id)
    if not q:
        # 检查是否已完成
        run = get_run(run_id)
        if run and run["status"] != "running":
            async def _done():
                yield f"data: {json.dumps({'msg': '已完成', 'step': 'done', 'pct': 100, 'status': run['status']}, ensure_ascii=False)}\n\n"
            return StreamingResponse(_done(), media_type="text/event-stream")
        raise HTTPException(404, "流水线不存在或已过期")

    async def _stream():
        while True:
            try:
                msg = q.get(timeout=0.5)
                yield f"data: {msg}\n\n"
                if '"step":"done"' in msg or '"step":"error"' in msg:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'msg': '', 'step': 'heartbeat', 'pct': -1})}\n\n"
                if run_id not in pipeline_queues:
                    break

    return StreamingResponse(_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/pipeline/runs")
def api_pipeline_runs(limit: int = 20):
    return get_runs(limit)


@app.get("/api/pipeline/runs/{run_id}")
def api_pipeline_run_detail(run_id: int):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404)
    # 附送该 run 的内容
    contents = get_contents(limit=50)
    run["contents"] = [c for c in contents if c.get("run_id") == run_id]
    return run


# ═══════════════════════════════════════════════════
#  内容管理 API
# ═══════════════════════════════════════════════════

@app.get("/api/contents")
def api_contents(date: str = None, column: str = None, limit: int = 50):
    return get_contents(date=date, column_key=column, limit=limit)


@app.get("/api/contents/{content_id}")
def api_content_detail(content_id: int):
    c = get_content(content_id)
    if not c:
        raise HTTPException(404)
    return c


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[int] = None


@app.put("/api/contents/{content_id}")
def api_content_update(content_id: int, body: ContentUpdate):
    c = get_content(content_id)
    if not c:
        raise HTTPException(404)
    update_content(content_id, title=body.title, content=body.content,
                   is_published=body.is_published)
    return {"status": "ok"}


@app.delete("/api/contents/{content_id}")
def api_content_delete(content_id: int):
    db = get_db()
    db.execute("DELETE FROM contents WHERE id=?", (content_id,))
    db.commit()
    return {"status": "ok"}


# ═══════════════════════════════════════════════════
#  归档 API
# ═══════════════════════════════════════════════════

@app.get("/api/archive/dates")
def api_archive_dates():
    return get_dates_with_content()


@app.get("/api/archive/{date}")
def api_archive_date(date: str):
    return get_contents(date=date)


# ═══════════════════════════════════════════════════
#  模型配置 API（复用现有）
# ═══════════════════════════════════════════════════

@app.get("/api/models")
def get_all_models():
    return _load_json(REGISTRY_PATH)["models"]


@app.get("/api/config")
def get_config():
    config = _load_json(CONFIG_PATH)
    registry = _load_json(REGISTRY_PATH)
    enriched = {"text_generation": {}, "image_generation": {}}
    for category in ["text_generation", "image_generation"]:
        for biz_key, biz in config.get(category, {}).items():
            model_key = biz["model_key"]
            model_category = "text" if category == "text_generation" else "image"
            model_info = registry["models"].get(model_category, {}).get(model_key, {})
            enriched[category][biz_key] = {**biz, "model_detail": model_info}
    return enriched


@app.put("/api/config")
async def update_config(request: Request):
    body = await request.json()
    category = body.get("category", "")
    business_type = body.get("business_type", "")
    model_key = body.get("model_key", "")
    config = _load_json(CONFIG_PATH)
    if category not in config or business_type not in config[category]:
        raise HTTPException(400)
    config[category][business_type]["model_key"] = model_key
    _save_json(CONFIG_PATH, config)
    return {"status": "ok"}


# ═══════════════════════════════════════════════════
#  启动
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n  🚀 iKnow — AI PM 内容引擎")
    print("  📡 http://localhost:8800")
    print("  📊 仪表盘  |  ⚙️ 流水线  |  📝 内容管理  |  📦 归档\n")
    uvicorn.run(app, host="0.0.0.0", port=8800, log_level="error")
