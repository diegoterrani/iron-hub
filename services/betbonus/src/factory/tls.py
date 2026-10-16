"""
TLS fingerprint rotation for anti-detection.

Uses curl_cffi (if available) to match Chrome 120+ TLS fingerprint.
Falls back to requests with randomized headers.
Each account gets a unique but plausible browser fingerprint.
"""

from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger("betbonus.factory.tls")

# Try curl_cffi for real TLS fingerprinting
try:
    from curl_cffi import requests as cffi_requests
    from curl_cffi.requests import BrowserType
    HAS_CURL_CFFI = True
except ImportError:
    import requests as cffi_requests  # type: ignore[no-redef]
    BrowserType = None  # type: ignore[assignment,misc]
    HAS_CURL_CFFI = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BrowserFingerprint:
    """A plausible Chrome 120+ browser fingerprint."""
    user_agent: str
    accept_language: str
    sec_ch_ua: str
    sec_ch_ua_platform: str
    sec_fetch_dest: str = "document"
    sec_fetch_mode: str = "navigate"
    sec_fetch_site: str = "none"
    sec_fetch_user: str = "?1"
    upgrade_insecure_requests: str = "1"
    connection: str = "keep-alive"
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"


# ---------------------------------------------------------------------------
# Chrome 120+ User-Agent pool (Win/Mac/Linux, various minor versions)
# ---------------------------------------------------------------------------

_CHROME_UA_POOL: list[str] = [
    # Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


# Sec-CH-UA platform values
_CHUA_PLATFORMS = [
    '"Windows"',
    '"macOS"',
    '"Linux"',
]

# Accept-Language values (Brazilian Portuguese)
_ACCEPT_LANGUAGES = [
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "pt-BR,pt;q=0.9,en;q=0.8",
    "pt-BR,pt;q=0.8,en-US;q=0.7,en;q=0.6",
    "pt,pt-BR;q=0.9,en;q=0.8",
    "pt-BR,pt;q=0.9",
]


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class TLSFingerprintManager:
    """Generates unique but plausible browser fingerprints per account.

    Parameters:
        seed: optional RNG seed for reproducible fingerprints
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._cache: dict[str, BrowserFingerprint] = {}

    def generate_fingerprint(self, account_id: str) -> BrowserFingerprint:
        """Generate a unique but plausible Chrome 120+ fingerprint.

        Deterministic per account_id (same account always gets same fingerprint).

        Args:
            account_id: unique identifier for the account

        Returns:
            BrowserFingerprint with all headers set
        """
        # Check cache
        if account_id in self._cache:
            return self._cache[account_id]

        # Derive a deterministic RNG from account_id
        digest = hashlib.sha256(account_id.encode()).digest()
        account_rng = random.Random(int.from_bytes(digest[:8], "big"))

        # Pick UA
        ua = account_rng.choice(_CHROME_UA_POOL)

        # Derive sec-ch-ua from the Chrome version in the UA
        import re
        match = re.search(r"Chrome/(\d+)\.(\d+)\.(\d+)\.(\d+)", ua)
        if match:
            major, minor = match.group(1), match.group(2)
            # Chrome 120+ reports sec-ch-ua with 3 entries
            sec_ch_ua = (
                f'Chromium;v="{major}", '
                f'Google Chrome;v="{major}", '
                f'Not-A.Brand;v="99"'
            )
        else:
            major, minor = "120", "0"
            sec_ch_ua = 'Chromium;v="120", Google Chrome;v="120", Not-A.Brand;v="99"'

        # Platform from UA
        if "Windows" in ua:
            platform = '"Windows"'
        elif "Macintosh" in ua:
            platform = '"macOS"'
        else:
            platform = '"Linux"'

        # Accept language
        accept_lang = account_rng.choice(_ACCEPT_LANGUAGES)

        fp = BrowserFingerprint(
            user_agent=ua,
            accept_language=accept_lang,
            sec_ch_ua=sec_ch_ua,
            sec_ch_ua_platform=platform,
            sec_fetch_dest="document",
            sec_fetch_mode="navigate",
            sec_fetch_site="none",
            sec_fetch_user="?1",
            upgrade_insecure_requests="1",
            connection="keep-alive",
            accept=(
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
        )

        self._cache[account_id] = fp
        return fp

    def create_session(
        self,
        account_id: str,
        proxy: Optional[str] = None,
    ) -> Any:
        """Create a requests.Session or curl_cffi Session with fingerprint headers.

        Args:
            account_id: account identifier (for deterministic fingerprint)
            proxy: optional proxy URL (http://host:port)

        Returns:
            A session object (requests.Session or curl_cffi Session)
        """
        fp = self.generate_fingerprint(account_id)
        headers = self.headers_dict(fp)

        if HAS_CURL_CFFI:
            try:
                session = cffi_requests.Session(
                    browser_type=BrowserType.CHROME,
                    impersonate="chrome",
                )
                session.headers.update(headers)
                if proxy:
                    session.proxies = {"http": proxy, "https": proxy}
                return session
            except Exception as e:
                log.warning("curl_cffi session failed (%s), falling back to requests", e)

        # Fallback: standard requests
        session = cffi_requests.Session()
        session.headers.update(headers)
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        return session

    def headers_dict(self, fingerprint: BrowserFingerprint) -> dict[str, str]:
        """Convert a BrowserFingerprint to a headers dict.

        Args:
            fingerprint: the fingerprint to convert

        Returns:
            Dict of HTTP headers
        """
        return {
            "User-Agent": fingerprint.user_agent,
            "Accept-Language": fingerprint.accept_language,
            "Sec-Ch-Ua": fingerprint.sec_ch_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": fingerprint.sec_ch_ua_platform,
            "Sec-Fetch-Dest": fingerprint.sec_fetch_dest,
            "Sec-Fetch-Mode": fingerprint.sec_fetch_mode,
            "Sec-Fetch-Site": fingerprint.sec_fetch_site,
            "Sec-Fetch-User": fingerprint.sec_fetch_user,
            "Upgrade-Insecure-Requests": fingerprint.upgrade_insecure_requests,
            "Connection": fingerprint.connection,
            "Accept": fingerprint.accept,
        }

    def user_agent_pool(self) -> list[str]:
        """Return the pool of realistic Chrome 120+ user agents.

        Returns:
            List of 20+ UA strings (Win/Mac/Linux, various minor versions)
        """
        return list(_CHROME_UA_POOL)

    def validate_fingerprint(self, fingerprint: BrowserFingerprint) -> bool:
        """Sanity-check a fingerprint for plausibility.

        Checks:
        - UA contains Chrome/120+ version
        - sec-ch-ua major matches UA major
        - platform matches UA OS
        - accept-language is non-empty

        Args:
            fingerprint: the fingerprint to validate

        Returns:
            True if the fingerprint passes all checks
        """
        import re

        # Check UA has Chrome 120+
        match = re.search(r"Chrome/(\d+)\.", fingerprint.user_agent)
        if not match:
            return False
        major = int(match.group(1))
        if major < 120:
            return False

        # Check sec-ch-ua major matches
        sec_match = re.search(r'Chromium;v="(\d+)"', fingerprint.sec_ch_ua)
        if not sec_match:
            return False
        if int(sec_match.group(1)) != major:
            return False

        # Check platform consistency
        if "Windows" in fingerprint.user_agent and '"Windows"' not in fingerprint.sec_ch_ua_platform:
            return False
        if "Macintosh" in fingerprint.user_agent and '"macOS"' not in fingerprint.sec_ch_ua_platform:
            return False
        if "Linux" in fingerprint.user_agent and '"Linux"' not in fingerprint.sec_ch_ua_platform:
            return False

        # Check accept-language
        if not fingerprint.accept_language:
            return False

        return True
