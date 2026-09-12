import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

from app.metadata.normalizer import (
    normalize_display_name,
    normalize_text,
    parse_int,
    parse_year,
)


@dataclass
class ExtractedMetadata:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    genre: str | None = None
    year: int | None = None
    track_number: int | None = None
    disc_number: int | None = None
    composer: str | None = None
    comments: str | None = None
    lyrics: str | None = None
    duration: float | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    codec: str | None = None
    artwork_bytes: bytes | None = None
    raw: dict = field(default_factory=dict)


def _first(values: list | tuple | str | None) -> str | None:
    if values is None:
        return None
    if isinstance(values, (list, tuple)):
        return str(values[0]) if values else None
    return str(values)


def extract_metadata(file_path: Path) -> ExtractedMetadata:
    result = ExtractedMetadata()
    suffix = file_path.suffix.lower()

    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is not None:
            tags = audio.tags or {}
            result.title = _first(tags.get("title"))
            result.artist = _first(tags.get("artist"))
            result.album = _first(tags.get("album"))
            result.album_artist = _first(tags.get("albumartist") or tags.get("album artist"))
            result.genre = _first(tags.get("genre"))
            result.composer = _first(tags.get("composer"))
            result.comments = _first(tags.get("comment"))
            result.year = parse_year(_first(tags.get("date")) or _first(tags.get("year")))
            result.track_number = parse_int(_first(tags.get("tracknumber")))
            result.disc_number = parse_int(_first(tags.get("discnumber"))) or 1
            if hasattr(audio.info, "length"):
                result.duration = float(audio.info.length)
            if hasattr(audio.info, "bitrate"):
                result.bitrate = int(audio.info.bitrate)
            if hasattr(audio.info, "sample_rate"):
                result.sample_rate = int(audio.info.sample_rate)
            if hasattr(audio.info, "channels"):
                result.channels = int(audio.info.channels)

        detailed = MutagenFile(file_path)
        if detailed is not None:
            result.codec = type(detailed).__name__
            if isinstance(detailed, MP3):
                id3 = ID3(file_path)
                result.raw["id3"] = {k: str(v) for k, v in list(id3.items())[:20]}
                if id3.get("USLT"):
                    result.lyrics = str(id3["USLT"].text)
            elif isinstance(detailed, MP4):
                result.raw["mp4"] = {k: str(v) for k, v in list(detailed.items())[:20]}
            elif isinstance(detailed, FLAC):
                result.raw["flac"] = {k: str(v) for k, v in list(detailed.items())[:20]}

        result.artwork_bytes = _extract_artwork(file_path, suffix)
    except Exception as exc:
        result.raw["error"] = str(exc)

    if not result.title:
        result.title = normalize_display_name(file_path.stem, file_path.stem)
    result.artist = normalize_display_name(result.artist, "Unknown Artist")
    result.album = normalize_display_name(result.album, "Unknown Album")
    return result


def _extract_artwork(file_path: Path, suffix: str) -> bytes | None:
    try:
        if suffix == ".mp3":
            id3 = ID3(file_path)
            for key in id3.keys():
                if key.startswith("APIC"):
                    return bytes(id3[key].data)
        audio = MutagenFile(file_path)
        if audio is None:
            return None
        if hasattr(audio, "tags") and audio.tags:
            for key in ("covr", "metadata_block_picture"):
                if key in audio.tags:
                    items = audio.tags[key]
                    if items:
                        item = items[0]
                        return bytes(getattr(item, "data", item))
        if isinstance(audio, FLAC) and audio.pictures:
            return bytes(audio.pictures[0].data)
    except Exception:
        return None
    return None


def compute_file_hash(file_path: Path, chunk_size: int = 65536) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_to_json(meta: ExtractedMetadata) -> str:
    payload = {
        "title": meta.title,
        "artist": meta.artist,
        "album": meta.album,
        "album_artist": meta.album_artist,
        "genre": meta.genre,
        "year": meta.year,
        "track_number": meta.track_number,
        "disc_number": meta.disc_number,
        "composer": meta.composer,
        "comments": meta.comments,
        "normalized_artist": normalize_text(meta.artist),
        "normalized_album": normalize_text(meta.album),
        "raw": meta.raw,
    }
    return json.dumps(payload)
