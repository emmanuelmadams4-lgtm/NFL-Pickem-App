"""The fixed list of permitted news feeds."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    host: str
    link_suffixes: tuple[str, ...]
    name: str = ""


SOURCES = (
    Source("espn", "https://www.espn.com/espn/rss/nfl/news", "www.espn.com", ("espn.com",), "ESPN"),
    Source(
        "cbs", "https://www.cbssports.com/rss/headlines/nfl/", "www.cbssports.com", ("cbssports.com",), "CBS Sports"
    ),
)
