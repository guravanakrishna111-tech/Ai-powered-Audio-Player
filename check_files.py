import sqlite3
import os
from pathlib import Path

db_path = Path('backend/data/library.db')
con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
cur = con.cursor()

songs = cur.execute("SELECT id, title, file_path, analysis_status FROM songs ORDER BY id").fetchall()
print(f"Total songs: {len(songs)}")

missing = []
ok = []
for s in songs:
    p = Path(s['file_path'])
    if p.exists():
        ok.append(dict(s))
    else:
        missing.append(dict(s))

print(f"\nOK (file exists): {len(ok)}")
print(f"MISSING (file not found): {len(missing)}")

if missing:
    print("\nSample MISSING paths:")
    for s in missing[:10]:
        print(f"  [{s['id']}] {s['file_path']}")

if ok:
    print("\nSample OK paths:")
    for s in ok[:5]:
        print(f"  [{s['id']}] {s['file_path']}")

# Check analysis status breakdown
statuses = cur.execute("SELECT analysis_status, count(*) as cnt FROM songs GROUP BY analysis_status").fetchall()
print("\nAnalysis status breakdown:")
for st in statuses:
    print(f"  {st['analysis_status']}: {st['cnt']}")

con.close()
