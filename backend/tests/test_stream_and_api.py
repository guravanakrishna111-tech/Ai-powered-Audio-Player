from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.connection import Database
from app.db.repository import LibraryRepository

client = TestClient(app)


def test_stream_nonexistent_song():
    response = client.get("/api/songs/999999/stream")
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_stream_valid_song():
    # Create a small dummy audio file in backend/data for permission safety
    test_data_dir = Path(__file__).parent.parent / "data"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = test_data_dir / "_test_dummy.mp3"
    dummy_file.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 200)

    from app.db.connection import db
    cur = db.execute(
        """
        INSERT INTO songs (file_path, file_size, file_mtime, title)
        VALUES (?, 210, 1000.0, 'Test Stream Song')
        """,
        (str(dummy_file.resolve()),),
    )
    song_id = cur.lastrowid

    try:
        response = client.get(f"/api/songs/{song_id}/stream")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "audio/mpeg"
        assert response.headers.get("accept-ranges") == "bytes"
        assert len(response.content) == 210
    finally:
        db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        try:
            dummy_file.unlink(missing_ok=True)
        except OSError:
            pass


def test_processing_routes():
    res_start = client.post("/api/processing/start")
    assert res_start.status_code == 200
    assert res_start.json().get("ok") is True

    res_prog = client.get("/api/processing/progress")
    assert res_prog.status_code == 200
    assert "audio_analysis" in res_prog.json()


def test_scan_workspace_route():
    res = client.post("/api/scan/workspace")
    assert res.status_code == 200
    assert res.json().get("ok") is True
