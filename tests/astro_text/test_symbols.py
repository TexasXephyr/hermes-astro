"""
Unit tests for astro_text.symbols lookup tables.
"""
import pytest

from astro_text.symbols import symbol_for_body, body_for_symbol, symbol_for_sign, sign_for_symbol
from astro_text.symbols import symbol_for_aspect, aspect_for_symbol, retrograde_symbol


class TestSymbolTables:
    def test_body_symbols_round_trip(self):
        glyph = symbol_for_body("Sun")
        assert glyph and isinstance(glyph, str)
        assert body_for_symbol(glyph) == "Sun"

    def test_sign_symbols_round_trip(self):
        glyph = symbol_for_sign("Aries")
        assert glyph and isinstance(glyph, str)
        assert sign_for_symbol(glyph) == "Aries"

    def test_aspect_symbols_round_trip(self):
        glyph = symbol_for_aspect("trine")
        assert glyph and isinstance(glyph, str)
        assert aspect_for_symbol(glyph) == "trine"

    def test_retrograde_symbol(self):
        sym = retrograde_symbol()
        assert isinstance(sym, str)
        assert len(sym) >= 1

    def test_unknown_body_returns_none(self):
        assert symbol_for_body("Eris-Not-Yet") is None

    def test_unknown_sign_raises(self):
        with pytest.raises(KeyError):
            symbol_for_sign("Ophiuchus")
