"""Fetch allowlisted JSON with pinned DNS and bounded response bodies."""

import ipaddress
import json
import logging
import queue
import socket
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

TIMEOUT_S = 10
DEADLINE_S = 20
MAX_BODY_BYTES = 2_000_000
RESOLVE_TIMEOUT_S = 5
ALLOWED_HOSTS = frozenset({"site.api.espn.com", "external-api.kalshi.com", "api.the-odds-api.com"})
USER_AGENT = "NFLPickemIntel/1.0 (private single-user app)"
_CREDIT_HEADERS = ("x-requests-remaining", "x-requests-last", "x-requests-used")
_NAT64 = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("::/96"),
    ipaddress.ip_network("2002::/16"),
    ipaddress.ip_network("2001::/32"),
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class FetchError(Exception):
    """A JSON reply could not be fetched safely."""


class Blocked(FetchError):
    """A security or access rule forbids this fetch."""


@dataclass(frozen=True)
class JsonResult:
    status: int
    data: Any
    headers: dict[str, str]


def _has_control(value: str) -> bool:
    return any(unicodedata.category(char).startswith("C") for char in value)


def default_resolver(host: str) -> list[str]:
    outcome: queue.Queue[list[str] | OSError] = queue.Queue(maxsize=1)

    def resolve() -> None:
        try:
            answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            addresses = list(dict.fromkeys(result[4][0] for result in answers))
            outcome.put(addresses)
        except Exception:
            outcome.put(OSError("dns error"))

    threading.Thread(target=resolve, name="nflpi-resolve", daemon=True).start()
    try:
        result = outcome.get(timeout=RESOLVE_TIMEOUT_S)
    except queue.Empty:
        raise OSError("dns timeout") from None
    if isinstance(result, OSError):
        raise result from None
    return result


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


def _checked_url(url: str) -> tuple[str, str]:
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        valid = (
            parts.scheme.lower() == "https"
            and hostname is not None
            and hostname.lower() in ALLOWED_HOSTS
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
    hostname = hostname.lower()
    return hostname, urlunsplit(("https", hostname, parts.path or "/", parts.query, ""))


def _pin(url: str, resolver: Callable[[str], list[str]]) -> tuple[str, str]:
    hostname, hostname_url = _checked_url(url)
    try:
        addresses = resolver(hostname)
    except Exception:
        raise FetchError("dns error") from None
    if not addresses:
        raise FetchError("dns empty")
    if any(not is_public(address) for address in addresses):
        raise Blocked("address blocked")
    address = next((item for item in addresses if isinstance(ipaddress.ip_address(item), ipaddress.IPv4Address)), None)
    address = address or addresses[0]
    ip_host = f"[{address}]" if ":" in address else address
    parts = urlsplit(hostname_url)
    return hostname, urlunsplit(("https", ip_host, parts.path, parts.query, ""))


def _read_body(response: httpx.Response, max_bytes: int, clock: Callable[[], float], deadline: float) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        if clock() > deadline:
            raise FetchError("deadline exceeded")
        size += len(chunk)
        if size > max_bytes:
            raise FetchError("too large")
        chunks.append(chunk)
    if clock() > deadline:
        raise FetchError("deadline exceeded")
    return b"".join(chunks)


def fetch_json(
    url: str,
    *,
    resolver: Callable[[str], list[str]] = default_resolver,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> JsonResult:
    deadline = clock() + DEADLINE_S
    if clock() > deadline:
        raise FetchError("deadline exceeded")
    hostname, ip_url = _pin(url, resolver)
    if clock() > deadline:
        raise FetchError("deadline exceeded")
    try:
        with build_client(transport) as client:
            with client.stream(
                "GET",
                ip_url,
                headers={"User-Agent": USER_AGENT, "Host": hostname, "Accept-Encoding": "identity"},
                extensions={"sni_hostname": hostname},
            ) as response:
                status = response.status_code
                if 300 <= status < 400:
                    raise FetchError("redirect")
                if status in (401, 403, 429):
                    raise Blocked(f"status {status}")
                if status != 200:
                    raise FetchError(f"status {status}")
                if "json" not in response.headers.get("content-type", "").lower():
                    raise FetchError("content type")
                encoding = response.headers.get("content-encoding", "")
                if any(part.strip().lower() not in ("", "identity") for part in encoding.split(",")):
                    raise FetchError("encoding")
                body = _read_body(response, MAX_BODY_BYTES, clock, deadline)
                headers = {name: response.headers[name] for name in _CREDIT_HEADERS if name in response.headers}
        try:
            data = json.loads(body)
        except Exception:
            raise FetchError("json") from None
        return JsonResult(status, data, headers)
    except FetchError:
        raise
    except Exception as exc:
        raise FetchError(type(exc).__name__) from None
