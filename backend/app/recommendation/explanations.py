from __future__ import annotations

from app.recommendation.models import ScoreBreakdown, SongFeatureVector


def build_reasons(source: SongFeatureVector, candidate: SongFeatureVector, breakdown: ScoreBreakdown) -> list[str]:
    reason_scores: list[tuple[float, str]] = []

    audio = breakdown.details.get("audio")
    if audio is not None and audio >= 0.65:
        for label, threshold in (("tempo", 0.78), ("energy", 0.74), ("timbre", 0.70), ("harmony", 0.72)):
            value = breakdown.details.get(f"audio_{label}")
            if value is not None and value >= threshold:
                reason_scores.append((value, _audio_reason(label)))

    mood = breakdown.details.get("mood")
    if mood is not None and mood >= 0.65:
        reason_scores.append((mood, "Similar mood profile"))

    genre = breakdown.details.get("genre")
    if genre is not None and genre > 0:
        shared = sorted(set(source.genres) & set(candidate.genres))
        if shared:
            reason_scores.append((genre, f"Shared genre: {shared[0]}"))

    artist = breakdown.details.get("artist")
    if artist == 1.0:
        reason_scores.append((artist, "Same artist"))

    language = breakdown.details.get("language")
    if language == 1.0:
        reason_scores.append((language, "Same language"))

    album = breakdown.details.get("album")
    if album == 1.0:
        reason_scores.append((album, "Same album"))
    elif album is not None and album >= 0.35:
        reason_scores.append((album, "Same album artist"))

    other = breakdown.details.get("other")
    if other is not None:
        composer = breakdown.details.get("other_composer")
        year = breakdown.details.get("other_year")
        duration = breakdown.details.get("other_duration")
        if composer == 1.0:
            reason_scores.append((composer, "Same composer"))
        if year is not None and year >= 0.70:
            reason_scores.append((year, "Similar release year"))
        if duration is not None and duration >= 0.70:
            reason_scores.append((duration, "Similar track length"))

    reason_scores.sort(key=lambda item: item[0], reverse=True)
    reasons: list[str] = []
    seen = set()
    for _, reason in reason_scores:
        if reason in seen:
            continue
        seen.add(reason)
        reasons.append(reason)
        if len(reasons) == 4:
            break
    return reasons


def _audio_reason(label: str) -> str:
    if label == "tempo":
        return "Similar tempo"
    if label == "energy":
        return "Similar energy"
    if label == "timbre":
        return "Similar timbral profile"
    if label == "harmony":
        return "Similar harmonic profile"
    return "Similar audio characteristics"

