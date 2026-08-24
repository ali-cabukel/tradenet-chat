from __future__ import annotations

from tradenet_chat.news import (
    _headline_from_google_title,
    _source_from_google_title,
    format_articles,
)


def test_format_articles_includes_source_and_url() -> None:
    text = format_articles(
        [
            {
                "title": "Wheat prices rise",
                "source": "Reuters",
                "published": "2026-08-24",
                "url": "https://example.com/wheat",
            }
        ],
        source="NewsAPI",
        query="Turkey wheat",
    )
    assert "via NewsAPI" in text
    assert "[Wheat prices rise](https://example.com/wheat)" in text
    assert "Reuters" in text


def test_format_articles_empty() -> None:
    assert "No recent headlines" in format_articles([], source="NewsAPI", query="x")


def test_google_title_split() -> None:
    title = "Ports congested - Financial Times"
    assert _headline_from_google_title(title) == "Ports congested"
    assert _source_from_google_title(title) == "Financial Times"
