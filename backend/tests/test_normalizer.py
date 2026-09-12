import pytest

from app.metadata.normalizer import normalize_text, normalize_display_name, parse_year


def test_normalize_text_collapses_whitespace_and_case():
    assert normalize_text("  The  Beatles ") == "the beatles"


def test_normalize_display_name_fallback():
    assert normalize_display_name(None) == "Unknown"
    assert normalize_display_name("  Daft Punk ") == "Daft Punk"


def test_parse_year_from_string():
    assert parse_year("1999") == 1999
    assert parse_year("Released 2012") == 2012
    assert parse_year("invalid") is None
