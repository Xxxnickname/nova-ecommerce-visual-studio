"""SQLite storage and schema migration."""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .config import APP_DIR

DB_PATH = Path(os.getenv("ECOMMERCE_DB_PATH", APP_DIR / "data" / "data.db"))
PRODUCTS_JSON = APP_DIR / "products.json"


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=8000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _columns(conn, table)
    for name, sql_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


def init_db() -> None:
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products(
          sku TEXT PRIMARY KEY, name TEXT, cost REAL, price REAL, stock INTEGER,
          status TEXT, updated_at TEXT, description TEXT, vendor TEXT,
          product_type TEXT, tags TEXT, seo_title TEXT, seo_description TEXT,
          image1 TEXT, image2 TEXT, weight_kg REAL, compare_at REAL,
          shopify_id TEXT, shopify_status TEXT, category TEXT,
          packed_length REAL, packed_width REAL, packed_height REAL,
          packed_unit TEXT, target_platform TEXT, platform_status TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, sku TEXT,
          old_value TEXT, new_value TEXT, status TEXT, message TEXT,
          created_at TEXT, finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS approvals(
          id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, sku TEXT,
          old_price REAL, new_price REAL, delta_pct REAL, status TEXT,
          created_at TEXT, decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS price_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, old_price REAL,
          new_price REAL, task_id INTEGER, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS logs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER, step TEXT,
          detail TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS generated_images(
          id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT NOT NULL, path TEXT NOT NULL,
          prompt TEXT, preset TEXT, style TEXT, template_id TEXT, source TEXT,
          width INTEGER, height INTEGER, file_size INTEGER, job_id INTEGER,
          published_media_id TEXT, published_at TEXT, created_at TEXT,
          platform_id TEXT, suite_id TEXT, asset_role TEXT,
          model_id TEXT, generation_resolution TEXT, category_id TEXT
        );
        CREATE TABLE IF NOT EXISTS image_jobs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, sku TEXT,
          status TEXT, params TEXT, result TEXT, error TEXT,
          created_at TEXT, finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_sku ON tasks(sku);
        CREATE INDEX IF NOT EXISTS idx_image_jobs_status ON image_jobs(status);
        CREATE TABLE IF NOT EXISTS product_images(
          id INTEGER PRIMARY KEY AUTOINCREMENT, product_sku TEXT NOT NULL,
          path TEXT NOT NULL, role TEXT, sort_order INTEGER DEFAULT 0,
          created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_images_sku ON generated_images(sku);
        CREATE INDEX IF NOT EXISTS idx_product_images_sku ON product_images(product_sku);
        """
    )
    _add_columns(
        conn,
        "products",
        {
            "description": "TEXT", "vendor": "TEXT", "product_type": "TEXT",
            "tags": "TEXT", "seo_title": "TEXT", "seo_description": "TEXT",
            "image1": "TEXT", "image2": "TEXT", "weight_kg": "REAL",
            "compare_at": "REAL", "shopify_id": "TEXT", "shopify_status": "TEXT",
            "category": "TEXT", "packed_length": "REAL", "packed_width": "REAL",
            "packed_height": "REAL", "packed_unit": "TEXT",
            "target_platform": "TEXT", "platform_status": "TEXT",
        },
    )
    _add_columns(
        conn,
        "generated_images",
        {"published_media_id": "TEXT", "published_at": "TEXT", "platform_id": "TEXT", "suite_id": "TEXT", "asset_role": "TEXT", "model_id": "TEXT", "generation_resolution": "TEXT", "category_id": "TEXT"},
    )
    _seed_products(conn)
    _backfill_products(conn)
    _recover_interrupted_jobs(conn)
    conn.execute("UPDATE products SET target_platform='shopify' WHERE target_platform IS NULL OR target_platform=''")
    conn.execute("UPDATE products SET platform_status='已发布' WHERE platform_status IS NULL AND shopify_id IS NOT NULL AND shopify_id != ''")
    conn.execute("UPDATE generated_images SET platform_id='shopify' WHERE platform_id IS NULL OR platform_id=''")
    conn.execute(
        """UPDATE generated_images SET category_id = CASE
             WHEN COALESCE(preset,'') LIKE 'beauty_%' OR COALESCE(template_id,'') LIKE 'beauty_%' THEN 'beauty'
             WHEN COALESCE(preset,'') IN ('living_room','bedroom','sofa','window') OR COALESCE(template_id,'') IN ('living_room','bedroom','sofa','window') THEN 'home_textile'
             ELSE COALESCE(NULLIF(category_id,''),'generic') END
           WHERE category_id IS NULL OR category_id=''"""
    )
    conn.commit()
    conn.close()


def _seed_products(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] or not PRODUCTS_JSON.exists():
        return
    try:
        products = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for p in products:
        images = p.get("images") or []
        conn.execute(
            """INSERT INTO products(
              sku,name,cost,price,stock,status,updated_at,description,vendor,product_type,
              tags,seo_title,seo_description,image1,image2,weight_kg,compare_at,
              shopify_id,shopify_status,category,packed_length,packed_width,packed_height,packed_unit
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                p["sku"], p["title"], float(p.get("cost", 0)), float(p.get("price", 0)),
                int(p.get("stock", 0)), "在售", now(), p.get("description_html", ""),
                p.get("vendor", ""), p.get("product_type", ""), ",".join(p.get("tags", [])),
                p.get("seo_title", ""), p.get("seo_description", ""),
                images[0] if images else "", images[1] if len(images) > 1 else "",
                float(p.get("weight_kg", 1.0)), float(p.get("compare_at_price") or 0),
                "", "", p.get("category", "gid://shopify/TaxonomyCategory/hg-15-1-4"),
                float(p.get("packed_length", 35)), float(p.get("packed_width", 25)),
                float(p.get("packed_height", 8)), p.get("packed_unit", "CENTIMETERS"),
            ),
        )



def _recover_interrupted_jobs(conn: sqlite3.Connection) -> None:
    """Background work is process-local; jobs left running after a restart cannot resume."""
    conn.execute(
        """UPDATE image_jobs
           SET status='failed', error=COALESCE(NULLIF(error,''), '服务重启，任务已中断，请重新生成'), finished_at=?
           WHERE status IN ('queued','running')""",
        (now(),),
    )
    conn.execute(
        """UPDATE tasks
           SET status='中断', message=COALESCE(NULLIF(message,''), '服务重启，执行状态未确认'), finished_at=?
           WHERE status='执行中'""",
        (now(),),
    )


def _backfill_products(conn: sqlite3.Connection) -> None:
    """Fill product metadata added after the original V1 database was created."""
    if not PRODUCTS_JSON.exists():
        return
    try:
        source = {item["sku"]: item for item in json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError, KeyError):
        return
    defaults = {
        "category": "gid://shopify/TaxonomyCategory/hg-15-1-4",
        "packed_length": 35,
        "packed_width": 25,
        "packed_height": 8,
        "packed_unit": "CENTIMETERS",
    }
    for sku, item in source.items():
        current = conn.execute(
            "SELECT category,packed_length,packed_width,packed_height,packed_unit FROM products WHERE sku=?",
            (sku,),
        ).fetchone()
        if not current:
            continue
        values = {
            "category": current[0] or item.get("category") or defaults["category"],
            "packed_length": current[1] if current[1] is not None else float(item.get("packed_length", defaults["packed_length"])),
            "packed_width": current[2] if current[2] is not None else float(item.get("packed_width", defaults["packed_width"])),
            "packed_height": current[3] if current[3] is not None else float(item.get("packed_height", defaults["packed_height"])),
            "packed_unit": current[4] or item.get("packed_unit") or defaults["packed_unit"],
        }
        conn.execute(
            "UPDATE products SET category=?,packed_length=?,packed_width=?,packed_height=?,packed_unit=? WHERE sku=?",
            (*values.values(), sku),
        )

def rows(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def add_task(conn: sqlite3.Connection, task_type: str, sku: str, old_value: str = "", new_value: str = "", status: str = "执行中") -> int:
    cursor = conn.execute(
        "INSERT INTO tasks(type,sku,old_value,new_value,status,message,created_at) VALUES(?,?,?,?,?,?,?)",
        (task_type, sku, old_value, new_value, status, "", now()),
    )
    return int(cursor.lastrowid)


def add_log(conn: sqlite3.Connection, task_id: int, step: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO logs(task_id,step,detail,created_at) VALUES(?,?,?,?)",
        (task_id, step, detail[:4000], now()),
    )


def finish_task(conn: sqlite3.Connection, task_id: int, status: str, message: str) -> None:
    conn.execute(
        "UPDATE tasks SET status=?,message=?,finished_at=? WHERE id=?",
        (status, message[:1000], now(), task_id),
    )
