"""Wikipedia lookup for country facts (population, GDP, capital, etc.)."""

from __future__ import annotations

import httpx

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
USER_AGENT = "tradenet-chat/0.1 (https://github.com/ali-cabukel/tradenet-chat)"

ISO3_TITLES = {
    "USA": "United States",
    "TUR": "Turkey",
    "DEU": "Germany",
    "GBR": "United Kingdom",
    "CHN": "China",
    "FRA": "France",
    "JPN": "Japan",
    "IND": "India",
    "ITA": "Italy",
    "ESP": "Spain",
    "NLD": "Netherlands",
    "CAN": "Canada",
    "AUS": "Australia",
    "BRA": "Brazil",
    "RUS": "Russia",
    "KOR": "South Korea",
    "MEX": "Mexico",
    "SAU": "Saudi Arabia",
    "ARE": "United Arab Emirates",
    "ZAF": "South Africa",
}


def resolve_title_hint(query: str) -> str:
    needle = query.strip()
    if len(needle) == 3 and needle.isalpha():
        return ISO3_TITLES.get(needle.upper(), needle)
    return needle


async def search_titles(query: str, *, limit: int = 3) -> list[str]:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get(WIKI_API, params=params)
        response.raise_for_status()
        hits = response.json().get("query", {}).get("search", [])
    return [str(hit["title"]) for hit in hits if hit.get("title")]


async def fetch_summary(title: str) -> dict[str, str]:
    url = WIKI_SUMMARY.format(title=title.replace(" ", "_"))
    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
    extract = str(payload.get("extract") or "").strip()
    description = str(payload.get("description") or "").strip()
    page_url = str((payload.get("content_urls") or {}).get("desktop", {}).get("page") or "")
    return {
        "title": str(payload.get("title") or title),
        "description": description,
        "extract": extract,
        "url": page_url,
    }


async def lookup_wikipedia(query: str) -> str:
    hint = resolve_title_hint(query)
    if not hint:
        return "Provide a country or topic to look up on Wikipedia."

    try:
        titles = await search_titles(hint)
        title = titles[0] if titles else hint
        page = await fetch_summary(title)
    except httpx.HTTPError as exc:
        return f"Wikipedia request failed: {exc}"

    if not page["extract"] and not page["description"]:
        return f"No Wikipedia summary found for '{hint}'."

    heading = f"**{page['title']}**"
    if page["description"]:
        heading += f" — {page['description']}"
    lines = [heading, ""]
    if page["extract"]:
        lines.append(page["extract"])
    if page["url"]:
        lines.extend(["", f"[Wikipedia]({page['url']})"])
    return "\n".join(lines)
