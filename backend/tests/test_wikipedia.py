from __future__ import annotations

from tradenet_chat.wikipedia import resolve_title_hint


def test_resolve_title_hint_maps_iso3() -> None:
    assert resolve_title_hint("TUR") == "Turkey"
    assert resolve_title_hint("usa") == "United States"
    assert resolve_title_hint("Germany") == "Germany"
    assert resolve_title_hint("  DEU ") == "Germany"
