import re
import unicodedata


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value.strip())
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def normalize_display_name(value: str | None, fallback: str = "Unknown") -> str:
    if not value or not value.strip():
        return fallback
    text = unicodedata.normalize("NFKC", value.strip())
    return re.sub(r"\s+", " ", text)


def parse_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1000 <= value <= 9999 else None
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group()) if match else None


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None
