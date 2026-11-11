import sqlite3
from pathlib import Path

db_path = Path('backend/data/library.db')
con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
cur = con.cursor()

# Check which Audio folder songs are in DB
audio_folder = Path('Audio folder').resolve()
audio_files = list(audio_folder.rglob('*.mp3'))
print(f"Audio folder has {len(audio_files)} mp3s")

# Check which ones are in DB
in_db = set()
for row in cur.execute("SELECT file_path FROM songs").fetchall():
    in_db.add(row['file_path'])

missing_from_db = []
for f in audio_files:
    fstr = str(f.resolve())
    if fstr not in in_db:
        missing_from_db.append(fstr)

print(f"In DB: {len(audio_files) - len(missing_from_db)}")
print(f"NOT in DB: {len(missing_from_db)}")
for p in missing_from_db[:5]:
    print(f"  MISSING: {p}")

# Also show all DB songs from Audio folder
audio_folder_songs = [r for r in cur.execute("SELECT id, title, analysis_status, file_path FROM songs").fetchall()
                       if 'Audio folder' in r['file_path']]
print(f"\nSongs from 'Audio folder' in DB: {len(audio_folder_songs)}")
for s in audio_folder_songs[:5]:
    print(f"  [{s['id']}] {s['title']} [{s['analysis_status']}]")

con.close()
