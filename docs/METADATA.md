# Metadata Pipeline

## Extraction (embedded)

Uses **mutagen** to read ID3, Vorbis, MP4, FLAC tags.

Fields extracted:

- title, artist, album, album artist, genre, year
- track/disc numbers, composer, comments, lyrics (when present)
- duration, bitrate, sample rate, channels, codec
- embedded artwork (saved to local `artwork/` directory)

## Normalization

`normalizer.py`:

- Unicode NFKC normalization
- Whitespace collapse
- Case-insensitive matching key (`normalized_name`)
- Prevents "The Beatles" vs "the  beatles" becoming separate artists

## Missing metadata

- Title falls back to filename stem
- Artist → "Unknown Artist", Album → "Unknown Album"
- All nullable fields supported in DB

## Online enrichment (optional)

**Provider:** MusicBrainz API (legitimate, no scraping)

Pipeline:

```
Local song → search query (title + artist) → MusicBrainz → validate → cache → update year/source
```

- Toggle in Settings
- Failures are silent; app continues offline
- Only minimal query text sent — **no audio upload**

## Limitations

- MusicBrainz match quality depends on metadata quality
- Rate limits apply (User-Agent required)
- No automatic overwrite of user-edited tags (future enhancement)
