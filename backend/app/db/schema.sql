-- AI Audio Player — SQLite schema (Part 1)

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    album_artist_id INTEGER REFERENCES artists(id),
    year INTEGER,
    artwork_path TEXT,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    UNIQUE(normalized_title, album_artist_id)
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,
    file_hash TEXT,
    title TEXT,
    artist_id INTEGER REFERENCES artists(id),
    album_id INTEGER REFERENCES albums(id),
    track_number INTEGER,
    disc_number INTEGER DEFAULT 1,
    duration REAL,
    artwork_path TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (analysis_status IN ('pending', 'processing', 'complete', 'failed', 'skipped')),
    is_missing INTEGER NOT NULL DEFAULT 0,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    play_count INTEGER NOT NULL DEFAULT 0,
    last_played_at REAL,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    updated_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS song_metadata (
    song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    album_artist TEXT,
    composer TEXT,
    comments TEXT,
    lyrics TEXT,
    bitrate INTEGER,
    sample_rate INTEGER,
    channels INTEGER,
    codec TEXT,
    source TEXT NOT NULL DEFAULT 'embedded',
    enriched_at REAL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS song_genres (
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (song_id, genre_id)
);

CREATE TABLE IF NOT EXISTS audio_features (
    song_id INTEGER PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    bpm REAL,
    tempo REAL,
    rms_energy REAL,
    loudness REAL,
    spectral_centroid REAL,
    spectral_bandwidth REAL,
    spectral_contrast_mean REAL,
    zero_crossing_rate REAL,
    mfcc_mean TEXT,
    chroma_mean TEXT,
    estimated_key TEXT,
    key_confidence REAL,
    mood_scores TEXT,
    feature_vector TEXT,
    analyzed_at REAL,
    analyzer_version TEXT NOT NULL DEFAULT '0.1.0'
);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (job_type IN ('metadata', 'analysis', 'enrichment', 'fingerprint')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'complete', 'failed', 'retry')),
    priority INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    error_message TEXT,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    started_at REAL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS music_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_scanned_at REAL,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    is_smart INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    updated_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    PRIMARY KEY (playlist_id, song_id)
);

CREATE TABLE IF NOT EXISTS duplicate_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id_a INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    song_id_b INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    similarity_score REAL NOT NULL,
    match_reason TEXT NOT NULL,
    reviewed INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    UNIQUE(song_id_a, song_id_b)
);

CREATE TABLE IF NOT EXISTS recommendation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    recommended_song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    reasons_json TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    algorithm_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec'))
);

CREATE TABLE IF NOT EXISTS enrichment_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lookup_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at REAL NOT NULL DEFAULT (unixepoch('subsec')),
    expires_at REAL
);

CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist_id);
CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album_id);
CREATE INDEX IF NOT EXISTS idx_songs_analysis_status ON songs(analysis_status);
CREATE INDEX IF NOT EXISTS idx_songs_file_hash ON songs(file_hash);
CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title);
CREATE INDEX IF NOT EXISTS idx_albums_artist ON albums(album_artist_id);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_duplicate_candidates_score ON duplicate_candidates(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_history_source ON recommendation_history(source_song_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_history_score ON recommendation_history(source_song_id, score DESC);
