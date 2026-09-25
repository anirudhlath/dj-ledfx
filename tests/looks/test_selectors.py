from __future__ import annotations

import pytest

from dj_ledfx.looks.selectors import Selector, parse_selector, selects


def test_selectors_are_ids_or_a_type_word() -> None:
    assert parse_selector("type:candle") == Selector("type", "candle")
    assert parse_selector(" Type:Candle ") == Selector("type", "candle")
    assert parse_selector("openrgb:localhost:6742:0") == Selector("id", "openrgb:localhost:6742:0")


@pytest.mark.parametrize("text", ["", "   ", "type:", "type:two words", "type:a/b"])
def test_bad_selectors_are_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse_selector(text)


def test_a_type_picks_lights_with_that_whole_word_in_their_name_or_model() -> None:
    candles = (parse_selector("type:candle"),)
    assert selects(candles, {"lamp-1"}, "Candle 1 Colour")
    assert selects(candles, {"lamp-1"}, "Hall light, candle")
    assert not selects(candles, {"lamp-1"}, "Candleholder")
    by_id = (parse_selector("lamp-2"), parse_selector("type:tube"))
    assert selects(by_id, {"lamp-2", "lamp-2-light"}, "Desk")
    assert not selects(by_id, {"lamp-3"}, "Desk")
