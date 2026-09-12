"""Metadata extraction package."""

from app.metadata.extractor import ExtractedMetadata, compute_file_hash, extract_metadata
from app.metadata.normalizer import normalize_display_name, normalize_text

__all__ = [
    "ExtractedMetadata",
    "compute_file_hash",
    "extract_metadata",
    "normalize_display_name",
    "normalize_text",
]
