import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db.connection import db

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings() -> dict:
    rows = db.fetchall("SELECT key, value FROM settings")
    stored = {row["key"]: row["value"] for row in rows}
    return {
        "auto_scan": stored.get("auto_scan", "true") == "true",
        "background_analysis": stored.get("background_analysis", "true") == "true",
        "enrichment_enabled": settings.enrichment_enabled,
        "music_folders": [dict(r) for r in db.fetchall("SELECT * FROM music_folders")],
        "data_dir": str(settings.data_dir),
    }


@router.put("/settings")
def update_settings(payload: dict) -> dict:
    for key in ("auto_scan", "background_analysis", "enrichment_enabled"):
        if key in payload:
            db.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, unixepoch('subsec'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(bool(payload[key])).lower()),
            )
            if key == "enrichment_enabled":
                settings.enrichment_enabled = bool(payload[key])
    return get_settings()


@router.post("/settings/clear-cache")
def clear_cache() -> dict:
    if settings.cache_dir.exists():
        shutil.rmtree(settings.cache_dir)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    db.execute("DELETE FROM enrichment_cache")
    return {"ok": True}


@router.post("/settings/reset-database")
def reset_database() -> dict:
    db_path = settings.db_path
    if db_path.exists():
        db_path.unlink()
    from app.db.connection import Database
    Database(db_path)
    return {"ok": True, "message": "Database reset. Restart scan to rebuild library."}
