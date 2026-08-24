"""News headlines from NewsAPI.org and search engines (DuckDuckGo, Google News RSS)."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

from tradenet_chat.settings import get_settings
from tradenet_chat.wikipedia import resolve_title_hint

USER_AGENT = "tradenet-chat/0.1 (https://github.com/ali-cabukel/tradenet-chat)"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _md_link_label(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def format_articles(articles: list[dict[str, str]], *, source: str, query: str) -> str:
    if not articles:
        return f"No recent headlines found for '{query}'."
    lines = [f"**Recent headlines about {query}** (via {source})", ""]
    for article in articles:
        title = article.get("title") or ""
        outlet = article.get("source") or ""
        published = article.get("published") or ""
        url = article.get("url") or ""
        suffix = ", ".join(part for part in (outlet, published) if part)
        label = _md_link_label(title)
        line = f"- [{label}]({url})" if url else f"- {label}"
        if suffix:
            line += f" — {suffix}"
        lines.append(line)
    return "\n".join(lines)


async def newsapi_search(query: str, *, max_articles: int = 5) -> str:
    hint = resolve_title_hint(query)
    if not hint:
        return "Provide a topic or country to search for news."

    settings = get_settings()
    api_key = (
        settings.news_api_key.get_secret_value() if settings.news_api_key else None
    )
    if not api_key:
        return (
            "NEWS_API_KEY is not set. Use search_engine_news, or add a NewsAPI.org "
            "key to backend/.env."
        )

    params = {
        "q": hint,
        "pageSize": max_articles,
        "sortBy": "publishedAt",
        "language": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(
                NEWSAPI_URL,
                params=params,
                headers={"X-Api-Key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        return f"NewsAPI request failed: {exc}"

    if payload.get("status") != "ok":
        return f"NewsAPI error: {payload.get('message', 'unknown error')}"

    articles = [_normalize_newsapi(item) for item in payload.get("articles") or []]
    articles = [item for item in articles if item["title"]][:max_articles]
    return format_articles(articles, source="NewsAPI", query=hint)


async def search_engine_news(query: str, *, max_articles: int = 5) -> str:
    hint = resolve_title_hint(query)
    if not hint:
        return "Provide a topic or country to search for news."

    try:
        articles = await asyncio.to_thread(_ddgs_news, hint, max_articles)
        if articles:
            return format_articles(articles, source="DuckDuckGo News", query=hint)
    except Exception as exc:
        ddgs_error = str(exc)
    else:
        ddgs_error = ""

    try:
        articles = await _google_news_rss(hint, max_articles=max_articles)
        if articles:
            return format_articles(articles, source="Google News", query=hint)
    except Exception as exc:
        rss_error = str(exc)
    else:
        rss_error = ""

    detail = "; ".join(part for part in (ddgs_error, rss_error) if part)
    suffix = f" ({detail})" if detail else ""
    return f"Could not fetch search-engine news for '{hint}'.{suffix}"


def _ddgs_news(query: str, max_articles: int) -> list[dict[str, str]]:
    from ddgs import DDGS

    raw = DDGS().news(query, max_results=max_articles) or []
    articles: list[dict[str, str]] = []
    for item in raw:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        articles.append(
            {
                "title": title,
                "source": str(item.get("source") or "").strip(),
                "published": str(item.get("date") or "").strip()[:16],
                "url": str(item.get("url") or item.get("href") or "").strip(),
            }
        )
    return articles[:max_articles]


async def _google_news_rss(query: str, *, max_articles: int) -> list[dict[str, str]]:
    url = f"{GOOGLE_NEWS_RSS}?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)

    articles: list[dict[str, str]] = []
    for item in root.findall(".//item")[:max_articles]:
        raw_title = (item.findtext("title") or "").strip()
        if not raw_title:
            continue
        articles.append(
            {
                "title": _headline_from_google_title(raw_title),
                "source": _source_from_google_title(raw_title),
                "published": (item.findtext("pubDate") or "").strip(),
                "url": (item.findtext("link") or "").strip(),
            }
        )
    return articles


def _normalize_newsapi(item: dict[str, Any]) -> dict[str, str]:
    title = str(item.get("title") or "").strip()
    if title == "[Removed]":
        title = ""
    return {
        "title": title,
        "source": str((item.get("source") or {}).get("name") or "").strip(),
        "published": str(item.get("publishedAt") or "")[:10],
        "url": str(item.get("url") or "").strip(),
    }


def _headline_from_google_title(title: str) -> str:
    if " - " not in title:
        return title
    return title.rsplit(" - ", 1)[0].strip()


def _source_from_google_title(title: str) -> str:
    if " - " not in title:
        return ""
    tail = title.rsplit(" - ", 1)[1].strip()
    if tail.startswith("("):
        return ""
    return tail.split(" (", 1)[0].strip()
