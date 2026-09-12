# Recommendation Engine

## Architecture

Part 2A adds a local content-based recommender in `backend/app/recommendation/`.

Flow:

`current song -> feature builder -> candidate generator -> similarity scoring -> weighted ranking -> top-N recommendations -> explanations`

Backend endpoint:

`GET /api/recommendations/{song_id}?limit=5`

The frontend uses that response to render AI recommendations on the Now Playing screen and to choose the next track when playback ends.

## Feature audit

| Feature | Available? | Source | Quality |
| --- | --- | --- | --- |
| BPM | Yes | `audio_features.bpm` / `tempo` | Good for analyzed songs, baseline beat tracker only |
| Energy | Yes | `audio_features.rms_energy`, `loudness`, `zero_crossing_rate` | Useful, but not perceptually calibrated |
| MFCC | Yes | `audio_features.mfcc_mean` | Compact timbral summary |
| Chroma | Yes | `audio_features.chroma_mean` | Compact harmonic summary |
| Key | Yes | `audio_features.estimated_key` | Heuristic baseline, not always reliable |
| Genre | Yes | `songs` + `song_genres` + `genres` | Depends on tags or enrichment |
| Artist | Yes | `songs.artist_id` + `artists` | Strong structural signal |
| Album | Yes | `songs.album_id` + `albums` | Strong but can over-constrain results |
| Language | Partial | `song_metadata.raw_json` if enrichment provides it | Not present in current embedded extraction |
| Mood | Yes | `audio_features.mood_scores` | Transparent heuristic baseline, not a trained classifier |

## Song representation

The backend builds a reusable internal representation:

- audio
- metadata
- mood
- semantic placeholder for future phases

The main data structure is `SongFeatureVector`.

It stores:

- scalar audio features
- vector audio descriptors
- categorical metadata
- probabilistic mood scores
- normalized external fields when available

## Feature normalization

Raw numeric values are not compared directly.

The recommender uses robust scaling:

- median as the center
- interquartile range as the scale

Why:

- audio libraries often contain outliers
- tempo, loudness, and centroid live on different scales
- robust scaling is stable when the library is small or skewed

Normalization parameters are persisted in SQLite under:

- `settings.recommendation_normalization_v1`

That keeps recommendation behavior consistent across runs.

## Similarity algorithms

### Audio similarity

Audio similarity is split into interpretable parts:

- tempo
- energy
- timbre
- harmony

Each part is normalized to a comparable range, then combined with weights.

### Metadata similarity

Metadata uses explicit categorical similarity:

- artist match
- album match
- genre overlap
- language match
- other metadata such as composer, year, and duration

### Mood similarity

Mood is treated as a probability vector over labels such as `happy`, `sad`, and `calm`.

The implementation compares mood vectors using cosine similarity.

### Vector similarity

MFCC and chroma summaries are compared with cosine similarity after compact averaging.

## Weight configuration

Baseline weights are centralized in `backend/app/recommendation/config.py`:

- audio: `0.40`
- mood: `0.25`
- genre: `0.15`
- artist: `0.08`
- language: `0.05`
- album: `0.04`
- other: `0.03`

These are starting values, not claims of optimality.

## Candidate generation

Candidate generation is separate from ranking.

The current implementation:

- pulls all local songs except the current one
- excludes missing files
- excludes exact duplicates via file hash and duplicate candidate records
- skips songs that score at or below zero

This is intentionally simple because the current library scale is small.

## Ranking

Each candidate gets:

- component similarities
- a weighted final score
- a short reason list

Only available components contribute to the denominator, so missing values do not create misleading penalties.

## Explanation generation

The recommender emits only explanations backed by actual feature comparisons, such as:

- Similar tempo
- Similar energy
- Similar timbral profile
- Similar harmonic profile
- Similar mood profile
- Same genre
- Same artist
- Same album
- Same language
- Similar release year
- Similar track length

## Evaluation and logging

Each recommendation request stores rows in `recommendation_history` with:

- source song
- recommended song
- rank
- score
- reasons
- candidate count
- latency
- algorithm version
- config version

This is the seed for later offline evaluation and user-feedback metrics.

## Limitations

- This is a content-based baseline, not personalized collaborative filtering.
- Mood is heuristic, not a trained emotional classifier.
- Language is usually absent unless later enrichment adds it.
- The current ranking is intentionally conservative and explainable rather than optimized.

## Future improvements

- cache normalized song vectors
- add vector search / ANN indexing for very large libraries
- add user preference signals and personalization
- learn weights from feedback data
- improve language and semantic metadata enrichment
- add diversity and novelty controls

