"""iKnow 数据层 — SQLite 持久化存储"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "iknow.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动创建表）"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    _init_tables(db)
    return db


def _init_tables(db: sqlite3.Connection):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            columns TEXT,
            sources_summary TEXT,
            output_dir TEXT,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            column_key TEXT NOT NULL,
            title TEXT,
            content TEXT,
            platform_versions TEXT,
            word_count INTEGER DEFAULT 0,
            image_path TEXT,
            created_at TEXT NOT NULL,
            date TEXT NOT NULL,
            is_published INTEGER DEFAULT 0,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
        );

        CREATE TABLE IF NOT EXISTS raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            source TEXT NOT NULL,
            item_count INTEGER DEFAULT 0,
            data_json TEXT,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
        );

        CREATE TABLE IF NOT EXISTS source_status (
            source TEXT PRIMARY KEY,
            last_fetch TEXT,
            item_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok',
            error_msg TEXT
        );

        CREATE TABLE IF NOT EXISTS scheduler_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO scheduler_config (key, value) VALUES ("enabled", "false");
        INSERT OR IGNORE INTO scheduler_config (key, value) VALUES ("time_utc", "02:00");
        INSERT OR IGNORE INTO scheduler_config (key, value) VALUES ("last_run_at", "");
        INSERT OR IGNORE INTO scheduler_config (key, value) VALUES ("last_run_status", "");
    """)
    db.commit()


# ─── Pipeline Runs ───────────────────────────

def create_run(columns: list[str]) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO pipeline_runs (started_at, status, columns) VALUES (?, 'running', ?)",
        (datetime.now().isoformat(), json.dumps(columns, ensure_ascii=False))
    )
    db.commit()
    return cur.lastrowid


def update_run(run_id: int, status: str, output_dir: str = "", 
               sources_summary: dict = None, error: str = ""):
    db = get_db()
    db.execute(
        """UPDATE pipeline_runs 
           SET status=?, finished_at=?, output_dir=?, sources_summary=?, error=?
           WHERE id=?""",
        (status, datetime.now().isoformat(), output_dir,
         json.dumps(sources_summary, ensure_ascii=False) if sources_summary else "{}",
         error, run_id)
    )
    db.commit()


def get_runs(limit: int = 20) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: int) -> Optional[dict]:
    db = get_db()
    row = db.execute("SELECT * FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


# ─── Contents ────────────────────────────────

def save_content(run_id: int, column_key: str, title: str, content: str,
                 platform_versions: dict = None, word_count: int = 0,
                 image_path: str = "", date: str = None):
    db = get_db()
    db.execute(
        """INSERT INTO contents (run_id, column_key, title, content, platform_versions,
           word_count, image_path, created_at, date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, column_key, title, content,
         json.dumps(platform_versions, ensure_ascii=False) if platform_versions else "{}",
         word_count, image_path,
         datetime.now().isoformat(),
         date or datetime.now().strftime("%Y-%m-%d"))
    )
    db.commit()


def get_contents(date: str = None, column_key: str = None, 
                 limit: int = 50) -> list[dict]:
    db = get_db()
    conditions = []
    params = []
    if date:
        conditions.append("date = ?")
        params.append(date)
    if column_key:
        conditions.append("column_key = ?")
        params.append(column_key)
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = db.execute(
        f"SELECT * FROM contents {where} ORDER BY id DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["platform_versions"] = json.loads(d.get("platform_versions", "{}"))
        results.append(d)
    return results


def get_content(content_id: int) -> Optional[dict]:
    db = get_db()
    row = db.execute("SELECT * FROM contents WHERE id=?", (content_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["platform_versions"] = json.loads(d.get("platform_versions", "{}"))
    return d


def update_content(content_id: int, title: str = None, content: str = None,
                   is_published: int = None):
    db = get_db()
    sets = []
    params = []
    if title is not None:
        sets.append("title=?")
        params.append(title)
    if content is not None:
        sets.append("content=?")
        params.append(content)
    if is_published is not None:
        sets.append("is_published=?")
        params.append(is_published)
    if sets:
        params.append(content_id)
        db.execute(f"UPDATE contents SET {', '.join(sets)} WHERE id=?", params)
        db.commit()


def get_dates_with_content() -> list[str]:
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT date FROM contents ORDER BY date DESC LIMIT 60"
    ).fetchall()
    return [r["date"] for r in rows]


def get_stats() -> dict:
    db = get_db()
    total_runs = db.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
    total_contents = db.execute("SELECT COUNT(*) FROM contents").fetchone()[0]
    latest = db.execute(
        "SELECT date FROM contents ORDER BY date DESC LIMIT 1"
    ).fetchone()
    latest_run = db.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {
        "total_runs": total_runs,
        "total_contents": total_contents,
        "latest_date": latest["date"] if latest else None,
        "latest_status": dict(latest_run) if latest_run else None,
    }


# ─── Raw Data ────────────────────────────────

def save_raw_data(run_id: int, source: str, data: list, item_count: int):
    db = get_db()
    db.execute(
        "INSERT INTO raw_data (run_id, source, item_count, data_json) VALUES (?, ?, ?, ?)",
        (run_id, source, item_count, json.dumps(data, ensure_ascii=False, default=str)[:1000000])
    )
    db.execute(
        """INSERT OR REPLACE INTO source_status (source, last_fetch, item_count, status)
           VALUES (?, ?, ?, 'ok')""",
        (source, datetime.now().isoformat(), item_count)
    )
    db.commit()


def get_source_status() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM source_status ORDER BY source").fetchall()
    return [dict(r) for r in rows]


def update_source_status(source: str, status: str, error_msg: str = ""):
    db = get_db()
    db.execute(
        """INSERT OR REPLACE INTO source_status (source, last_fetch, status, error_msg)
           VALUES (?, ?, ?, ?)""",
        (source, datetime.now().isoformat(), status, error_msg)
    )
    db.commit()


print(f"✅ 数据库初始化完成: {DB_PATH}")


# ─── 调度器配置 ─────────────────────────────────

def get_scheduler_config() -> dict:
    db = get_db()
    rows = db.execute("SELECT key, value FROM scheduler_config").fetchall()
    db.close()
    return {row["key"]: row["value"] for row in rows}


def set_scheduler_config(key: str, value: str) -> dict:
    db = get_db()
    db.execute("""
        INSERT INTO scheduler_config (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, [key, value])
    db.commit()
    db.close()
    return get_scheduler_config()


def record_scheduler_run(status: str):
    set_scheduler_config("last_run_at", datetime.now().isoformat())
    set_scheduler_config("last_run_status", status)
