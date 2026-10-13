"""Turn bounded feed bytes into clean, allowlisted news items."""

import io
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

import feedparser

from nflpi.ingestion.news.sources import Source

_URL_SAFE = "/%:@!$&'()*+,;=-._~?"
_TRACKERS = {"fbclid", "gclid", "ocid"}


class FeedError(Exception):
    """The response is not a usable feed."""


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    published_at: datetime | None
    extract: str


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def clean_text(raw: str, limit: int) -> str:
    parser = _Text()
    parser.feed(raw)
    parser.close()
    text = " ".join("".join(parser.parts).split())
    text = "".join(char for char in text if not unicodedata.category(char).startswith("C"))
    return " ".join(text.split())[:limit].strip()


def canonical_url(link: str | None, suffixes: tuple[str, ...]) -> str | None:
    if not link or any(char.isspace() or unicodedata.category(char).startswith("C") for char in link) or "\\" in link:
        return None
    try:
        parts = urlsplit(link)
        host = parts.hostname
        if host is None:
            return None
        host.encode("ascii")
        if (
            parts.scheme.lower() != "https"
            or parts.username is not None
            or parts.password is not None
            or parts.netloc.lower() != host
            or host.endswith(".")
            or not any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)
        ):
            return None
    except (ValueError, UnicodeError):
        return None
    query_parts = []
    for segment in parts.query.split("&"):
        key = unquote_plus(segment.split("=", 1)[0]).lower()
        if not key.startswith("utm_") and key not in _TRACKERS:
            query_parts.append(segment)
    path = quote(parts.path or "/", safe=_URL_SAFE)
    query = quote("&".join(query_parts), safe=_URL_SAFE)
    result = urlunsplit(("https", host, path, query, ""))
    return result if len(result) <= 2048 else None


def _published(entry: dict, now: datetime) -> datetime | None:
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return None
    try:
        published = datetime(*stamp[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None
    return None if published > now + timedelta(days=1) else published


def parse_feed(body: bytes, source: Source, now: datetime) -> list[Item]:
    parsed = feedparser.parse(io.BytesIO(body))
    if not parsed.entries and (parsed.bozo or not parsed.get("version")):
        raise FeedError("not a feed")
    items: list[Item] = []
    usable = False
    for entry in parsed.entries[:100]:
        title = clean_text(entry.get("title") or "", 200)
        url = canonical_url(entry.get("link"), source.link_suffixes)
        if not title or not url:
            continue
        usable = True
        published_at = _published(entry, now)
        if published_at is not None and published_at < now - timedelta(days=30):
            continue
        items.append(Item(title, url, published_at, clean_text(entry.get("summary") or "", 300)))
    if parsed.entries and not usable:
        raise FeedError("no usable items")
    return items
