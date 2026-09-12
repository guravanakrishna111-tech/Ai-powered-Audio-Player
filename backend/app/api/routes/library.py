from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.repository import LibraryRepository
from app.db.connection import db
from app.services import scanner

router = APIRouter(tags=["library"])
repo = LibraryRepository(db)


@router.get("/songs")
def list_songs(
    search: str | None = Query(None),
    artist_id: int | None = Query(None),
    album_id: int | None = Query(None),
    favorites: bool = Query(False),
    limit: int = Query(500, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    songs = repo.get_songs(search, artist_id, album_id, favorites, limit, offset)
    return {"songs": songs, "count": len(songs)}


@router.get("/songs/{song_id}")
def get_song(song_id: int) -> dict:
    song = repo.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@router.post("/songs/{song_id}/favorite")
def toggle_favorite(song_id: int) -> dict:
    is_favorite = repo.toggle_favorite(song_id)
    return {"song_id": song_id, "is_favorite": is_favorite}


@router.post("/songs/{song_id}/played")
def record_play(song_id: int) -> dict:
    repo.record_play(song_id)
    return {"ok": True}


@router.get("/artists")
def list_artists() -> dict:
    return {"artists": repo.get_artists()}


@router.get("/albums")
def list_albums() -> dict:
    return {"albums": repo.get_albums()}


@router.get("/duplicates")
def list_duplicates() -> dict:
    return {"duplicates": repo.get_duplicates()}


@router.get("/folders")
def list_folders() -> dict:
    return {"folders": scanner.list_folders()}


@router.post("/folders")
def add_folder(payload: dict) -> dict:
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    scanner.add_folder(path)
    return {"ok": True, "folders": scanner.list_folders()}


@router.delete("/folders/{folder_id}")
def remove_folder(folder_id: int) -> dict:
    scanner.remove_folder(folder_id)
    return {"ok": True}


@router.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(scanner.scan_all)
    return {"ok": True, "message": "Scan started in background"}


@router.get("/scan/progress")
def scan_progress() -> dict:
    p = scanner.progress
    return {
        "total_files": p.total_files,
        "scanned": p.scanned,
        "added": p.added,
        "updated": p.updated,
        "skipped": p.skipped,
        "errors": p.errors,
        "is_scanning": p.is_scanning,
    }
