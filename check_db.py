import sqlite3
import os
from pathlib import Path

db_path = Path('backend/data/library.db')
print(f"DB exists: {db_path.exists()}, size: {db_path.stat().st_size if db_path.exists() else 0}")

con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

if 'songs' in tables:
    count = cur.execute("SELECT count(*) FROM songs").fetchone()[0]
    print(f"Songs count: {count}")
    if count > 0:
        songs = cur.execute("SELECT id, title, file_path, analysis_status FROM songs LIMIT 5").fetchall()
        for s in songs:
            print(dict(s))

if 'music_folders' in tables:
    folders = cur.execute("SELECT * FROM music_folders").fetchall()
    print("Folders:", [dict(f) for f in folders])

if 'analysis_jobs' in tables:
    jobs = cur.execute("SELECT status, count(*) as cnt FROM analysis_jobs GROUP BY status").fetchall()
    print("Analysis jobs:", [dict(j) for j in jobs])

con.close()
