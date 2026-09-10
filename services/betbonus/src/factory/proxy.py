"""Proxy rotation layer for IP diversity in bulk registration.

Supports a list of HTTP/HTTPS proxies (host:port or full URL) and rotates
through them to avoid IP-based rate limiting or fraud detection.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProxyEntry:
    """A single proxy endpoint."""
    scheme: str = "http"
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""

    def to_url(self) -> str:
        """Return the full proxy URL for use in requests."""
        auth = ""
        if self.username:
            auth = f"{self.username}:{self.password}@" if self.password else f"{self.username}@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

    @classmethod
    def parse(cls, raw: str) -> "ProxyEntry":
        """Parse a proxy string like 'http://user:pass@host:port' or 'host:port'."""
        entry = cls()
        text = raw.strip()
        if "://" in text:
            scheme, rest = text.split("://", 1)
            entry.scheme = scheme.lower()
            text = rest
        if "@" in text:
            auth, hostport = text.split("@", 1)
            if ":" in auth:
                entry.username, entry.password = auth.split(":", 1)
            else:
                entry.username = auth
            text = hostport
        if ":" in text:
            entry.host, port_str = text.rsplit(":", 1)
            entry.port = int(port_str)
        else:
            entry.host = text
            entry.port = 80 if entry.scheme == "http" else 443
        return entry


class ProxyPool:
    """Rotating proxy pool for outbound requests.

    Usage:
        pool = ProxyPool.from_env()  # reads BETBONUS_PROXIES
        proxy = pool.next()          # returns URL or None if no proxies
    """

    def __init__(self, proxies: Optional[list[str]] = None, seed: Optional[int] = None):
        self.entries: list[ProxyEntry] = []
        for raw in proxies or []:
            self.entries.append(ProxyEntry.parse(raw))
        self.rng = random.Random(seed)
        self._cursor = 0

    @classmethod
    def from_env(cls, env_var: str = "BETBONUS_PROXIES") -> "ProxyPool":
        """Create a pool from a comma-separated env var."""
        import os
        raw = os.environ.get(env_var, "")
        if not raw.strip():
            return cls([])
        proxies = [p.strip() for p in raw.split(",") if p.strip()]
        return cls(proxies)

    def next(self) -> Optional[str]:
        """Return the next proxy URL (round-robin), or None if pool is empty."""
        if not self.entries:
            return None
        url = self.entries[self._cursor % len(self.entries)].to_url()
        self._cursor += 1
        return url

    def random(self) -> Optional[str]:
        """Return a random proxy URL, or None if pool is empty."""
        if not self.entries:
            return None
        return self.rng.choice(self.entries).to_url()

    def requests_proxies(self) -> Optional[dict]:
        """Return a `proxies` dict for the `requests` library, or None."""
        url = self.next()
        if not url:
            return None
        return {"http": url, "https": url}

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return len(self.entries) > 0
