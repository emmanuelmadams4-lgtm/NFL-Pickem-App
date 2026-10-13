"""Fetch allowlisted feeds with pinned DNS, bounded bodies, and robots checks."""

import ipaddress
import socket
import ssl
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from nflpi.config import get_settings
from nflpi.ingestion.news.sources import Source

TIMEOUT_S = 10
DEADLINE_S = 20
MAX_FEED_BYTES = 2_000_000
MAX_ROBOTS_BYTES = 512_000
MAX_REDIRECTS = 3
MAX_VALIDATOR_LEN = 256
_NAT64 = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("::/96"),
    ipaddress.ip_network("2002::/16"),
    ipaddress.ip_network("2001::/32"),
)
_REDIRECTS = {301, 302, 303, 307, 308}


class FetchError(Exception):
    """A feed could not be fetched safely."""


class Blocked(FetchError):
    """A security or source access rule forbids this fetch."""


@dataclass(frozen=True)
class FetchResult:
    status: int
    body: bytes
    etag: str | None
    last_modified: str | None


def _has_control(value: str) -> bool:
    return any(unicodedata.category(char).startswith("C") for char in value)


def _validator(value: str | None) -> str | None:
    return (
        value
        if isinstance(value, str) and len(value) <= MAX_VALIDATOR_LEN and value.isascii() and value.isprintable()
        else None
    )


def user_agent() -> str:
    base = "NFLPickemIntel/1.0 (private single-user app"
    contact = get_settings().news_contact
    return f"{base}; contact: {contact})" if contact and not _has_control(contact) else f"{base})"


def default_resolver(host: str) -> list[str]:
    addresses: list[str] = []
    for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = result[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses


def build_client(transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(transport=transport, trust_env=False, follow_redirects=False, timeout=TIMEOUT_S)


def is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif any(ip in network for network in _NAT64):
            return False
    return ip.is_global and not ip.is_multicast


def _checked_url(url: str, host: str) -> tuple[str, str]:
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        valid = (
            parts.scheme.lower() == "https"
            and hostname is not None
            and hostname.lower() == host.lower()
            and parts.username is None
            and parts.password is None
            and parts.port in (None, 443)
            and not _has_control(url)
            and "\\" not in url
        )
    except (ValueError, UnicodeError):
        valid = False
        hostname = None
    if not valid or hostname is None:
        raise Blocked("url blocked")
    return hostname, urlunsplit(("https", hostname, parts.path or "/", parts.query, ""))


def fetch_guarded(
    url: str,
    *,
    host: str,
    resolver=default_resolver,
    transport: httpx.BaseTransport | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = MAX_FEED_BYTES,
    content_types: tuple[str, ...] = ("xml",),
    max_redirects: int = MAX_REDIRECTS,
    clock=time.monotonic,
) -> FetchResult:
    start = clock()
    redirects = 0
    with build_client(transport) as client:
        while True:
            if clock() > start + DEADLINE_S:
                raise FetchError("deadline exceeded")
            hostname, hostname_url = _checked_url(url, host)
            try:
                addresses = resolver(hostname)
            except (OSError, UnicodeError) as exc:
                raise FetchError("dns error") from exc
            if not addresses:
                raise FetchError("dns empty")
            if any(not is_public(address) for address in addresses):
                raise Blocked("address blocked")
            if clock() > start + DEADLINE_S:
                raise FetchError("deadline exceeded")
            address = addresses[0]
            ip_host = f"[{address}]" if ":" in address else address
            parts = urlsplit(hostname_url)
            ip_url = urlunsplit(("https", ip_host, parts.path, parts.query, ""))
            request_headers = httpx.Headers(headers or {})
            request_headers["User-Agent"] = user_agent()
            request_headers["Host"] = hostname
            request_headers["Accept-Encoding"] = "identity"
            try:
                with client.stream(
                    "GET", ip_url, headers=request_headers, extensions={"sni_hostname": hostname}
                ) as response:
                    status = response.status_code
                    if status in _REDIRECTS and "location" in response.headers:
                        if redirects >= max_redirects:
                            raise FetchError("too many redirects")
                        location = response.headers["location"]
                        if _has_control(location) or "\\" in location:
                            raise Blocked("url blocked")
                        try:
                            url = urljoin(hostname_url, location)
                        except (ValueError, UnicodeError) as exc:
                            raise Blocked("url blocked") from exc
                        redirects += 1
                        continue
                    if status in (401, 403, 429):
                        raise Blocked(f"status {status}")
                    if status >= 400 and status not in (404, 410):
                        raise FetchError(f"status {status}")
                    if status == 200:
                        media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                        if not any(kind in media_type for kind in content_types):
                            raise FetchError("content type")
                    if status in (304, 404, 410):
                        body = b""
                    elif 200 <= status < 300:
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_bytes():
                            if clock() > start + DEADLINE_S:
                                raise FetchError("deadline exceeded")
                            size += len(chunk)
                            if size > max_bytes:
                                raise FetchError("too large")
                            chunks.append(chunk)
                        body = b"".join(chunks)
                    else:
                        raise FetchError(f"status {status}")
                    return FetchResult(
                        status,
                        body,
                        _validator(response.headers.get("etag")),
                        _validator(response.headers.get("last-modified")),
                    )
            except (httpx.HTTPError, ssl.SSLError, OSError) as exc:
                raise FetchError(type(exc).__name__) from exc


def check_robots(source: Source, *, resolver=default_resolver, transport: httpx.BaseTransport | None = None) -> None:
    try:
        result = fetch_guarded(
            f"https://{source.host}/robots.txt",
            host=source.host,
            resolver=resolver,
            transport=transport,
            content_types=("text/plain",),
            max_bytes=MAX_ROBOTS_BYTES,
            max_redirects=0,
        )
    except Blocked:
        raise
    except FetchError as exc:
        raise FetchError("robots unavailable") from exc
    if result.status in (404, 410):
        return
    if result.status != 200:
        raise FetchError("robots unavailable")
    parser = RobotFileParser()
    parser.parse(result.body.decode("utf-8", "replace").splitlines())
    if not parser.can_fetch("NFLPickemIntel", source.url):
        raise Blocked("robots disallow")


def fetch_feed(
    source: Source,
    *,
    resolver=default_resolver,
    transport: httpx.BaseTransport | None = None,
    validators: dict[str, str] | None = None,
) -> FetchResult:
    check_robots(source, resolver=resolver, transport=transport)
    conditional: dict[str, str] = {}
    if validators:
        etag = _validator(validators.get("etag"))
        last_modified = _validator(validators.get("last_modified"))
        if etag is not None:
            conditional["If-None-Match"] = etag
        if last_modified is not None:
            conditional["If-Modified-Since"] = last_modified
    result = fetch_guarded(
        source.url,
        host=source.host,
        resolver=resolver,
        transport=transport,
        headers=conditional,
        content_types=("xml",),
    )
    if result.status not in (200, 304):
        raise FetchError(f"status {result.status}")
    return result
