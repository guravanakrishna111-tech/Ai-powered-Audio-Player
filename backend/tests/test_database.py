import tempfile
from pathlib import Path

from app.db.connection import Database


def test_schema_creates_core_tables():
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "schema_test.db")
    tables = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {row["name"] for row in tables}
    for expected in ("songs", "artists", "albums", "audio_features", "analysis_jobs"):
        assert expected in names
