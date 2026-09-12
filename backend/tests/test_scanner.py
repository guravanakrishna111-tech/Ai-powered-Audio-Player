import tempfile
import wave
from pathlib import Path

import pytest

from app.db.connection import Database
from app.scanner.library_scanner import LibraryScanner


def _create_wav(path: Path, duration_frames: int = 22050) -> None:
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x00\x00" * duration_frames)


@pytest.fixture
def temp_library():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "test.db"
        music_dir = root / "music"
        music_dir.mkdir()
        _create_wav(music_dir / "track_one.wav")
        _create_wav(music_dir / "track_two.wav")
        db = Database(db_path)
        scanner = LibraryScanner(db)
        scanner.add_folder(str(music_dir))
        yield scanner, db, music_dir


def test_scan_discovers_and_indexes_files(temp_library):
    scanner, db, _ = temp_library
    progress = scanner.scan_all()
    assert progress.total_files == 2
    assert progress.added == 2
    songs = db.fetchall("SELECT id, title, file_path FROM songs")
    assert len(songs) == 2


def test_rescan_skips_unchanged_files(temp_library):
    scanner, db, _ = temp_library
    scanner.scan_all()
    progress = scanner.scan_all()
    assert progress.skipped == 2
    assert progress.added == 0
