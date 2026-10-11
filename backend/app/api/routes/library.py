import mimetypes
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.db.repository import LibraryRepository
from app.db.connection import db
from app.services import scanner, engine

router = APIRouter(tags=["library"])
repo = LibraryRepository(db)

# Workspace root detection (assuming backend is in <root>/backend)
_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


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


@router.get("/songs/{song_id}/stream")
def stream_song(song_id: int):
    """Stream audio file for a song with HTTP Range request support."""
    song = repo.get_song(song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")

    file_path = Path(song["file_path"])
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio file not found on disk: {file_path}")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type or not mime_type.startswith("audio/"):
        suffix = file_path.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".flac": "audio/flac",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".aac": "audio/mp4",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
        }
        mime_type = mime_map.get(suffix, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=file_path.name,
    )


@router.get("/songs/{song_id}/artwork")
def get_song_artwork(song_id: int):
    """Serve embedded/cached artwork for a song."""
    song = repo.get_song(song_id)
    if not song or not song.get("artwork_path"):
        raise HTTPException(status_code=404, detail="Artwork not found")

    art_path = Path(song["artwork_path"])
    if not art_path.is_file():
        raise HTTPException(status_code=404, detail="Artwork file not found")

    mime, _ = mimetypes.guess_type(str(art_path))
    return FileResponse(path=art_path, media_type=mime or "image/jpeg")


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


def _resolve_folder(path_str: str) -> Path:
    clean = path_str.strip().strip('"').strip("'")
    p = Path(clean)
    if p.is_dir():
        return p.resolve()

    # Try relative to workspace
    cand = _WORKSPACE_ROOT / clean
    if cand.is_dir():
        return cand.resolve()

    # Try relative to current working directory parent
    cand2 = Path.cwd().parent / clean
    if cand2.is_dir():
        return cand2.resolve()

    # Try relative to current working directory
    cand3 = Path.cwd() / clean
    if cand3.is_dir():
        return cand3.resolve()

    raise HTTPException(status_code=400, detail=f"Folder not found: {path_str}")


@router.post("/folders")
def add_folder(payload: dict, background_tasks: BackgroundTasks) -> dict:
    raw_path = payload.get("path")
    if not raw_path:
        raise HTTPException(status_code=400, detail="path is required")

    resolved_path = _resolve_folder(raw_path)
    scanner.add_folder(str(resolved_path))

    # Auto trigger scan and ensure processing engine is running
    background_tasks.add_task(scanner.scan_all)
    engine.start()

    return {"ok": True, "added_path": str(resolved_path), "folders": scanner.list_folders()}


@router.post("/scan/workspace")
def scan_workspace(background_tasks: BackgroundTasks) -> dict:
    """Discover workspace audio folders (such as 'Audio folder') and scan them."""
    candidates = [
        _WORKSPACE_ROOT / "Audio folder",
        Path.cwd().parent / "Audio folder",
        Path.cwd() / "Audio folder",
    ]
    added = []
    for c in candidates:
        if c.is_dir():
            resolved = str(c.resolve())
            scanner.add_folder(resolved)
            added.append(resolved)
            break

    background_tasks.add_task(scanner.scan_all)
    engine.start()
    return {"ok": True, "added": added, "folders": scanner.list_folders()}


@router.delete("/folders/{folder_id}")
def remove_folder(folder_id: int) -> dict:
    scanner.remove_folder(folder_id)
    return {"ok": True}


@router.post("/scan")
def trigger_scan(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(scanner.scan_all)
    engine.start()
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
