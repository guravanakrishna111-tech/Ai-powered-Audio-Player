# Database Schema

SQLite is used in WAL mode. The schema lives in `backend/app/db/schema.sql`.

## Core entities

| Table | Purpose |
| --- | --- |
| `songs` | Stable song ID, file identity, analysis status |
| `artists` | Normalized artist entities |
| `albums` | Album grouping with optional artwork |
| `genres` | Genre vocabulary |
| `song_metadata` | Extended tags, codec info, enrichment source |
| `audio_features` | Extracted features, mood, and unified vector |
| `analysis_jobs` | Background job queue |
| `music_folders` | Watched directories |
| `playlists` / `playlist_songs` | User playlists |
| `duplicate_candidates` | Possible duplicates, never auto-deleted |
| `recommendation_history` | Logged recommendations, scores, ranks, and reasons |
| `enrichment_cache` | API response cache |
| `settings` | Key-value app settings |

## Change detection

Files are reprocessed when:

- Path is new
- `file_size` changes
- `file_mtime` changes

Unchanged files skip metadata and audio re-extraction.

## Indexes

- `songs(artist_id)`, `songs(album_id)`, `songs(analysis_status)`, `songs(file_hash)`
- `analysis_jobs(status, priority DESC)`
- `duplicate_candidates(similarity_score DESC)`
- `recommendation_history(source_song_id, score DESC)`

## Stable IDs

Each song receives an auto-increment `id` at first index. File path is unique, but the internal ID is used for playback, features, recommendations, and audits.

## Recommendation persistence

- `settings.recommendation_normalization_v1` stores robust scaling statistics for numeric recommendation features.
- `recommendation_history` stores the source song, recommended song, score, rank, reasons, candidate count, latency, and algorithm/configuration version for later evaluation.

