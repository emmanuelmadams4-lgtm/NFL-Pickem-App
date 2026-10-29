"""The compose file publishes ports on this computer only. Tailscale Serve reaches the app at 127.0.0.1:8000.

A published port on 0.0.0.0 skips the firewall, so the database or the app would be open on every interface.
"""

import re
from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_every_published_port_is_bound_to_localhost():
    ports = re.findall(r'^\s*-\s*"([^"]+:\d+)"\s*$', COMPOSE.read_text(), re.MULTILINE)  # "host:${PORT:-n}:n"
    assert len(ports) == 2, f"expected the db and app ports, found {ports}"
    assert all(p.startswith("127.0.0.1:") for p in ports), f"published on all interfaces: {ports}"
