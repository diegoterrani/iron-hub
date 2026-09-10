"""Multi-account orchestrator: register, login, and run kill chain across accounts.

The AccountFactory ties together:
- IdentityGenerator (synthetic BR identities)
- ProxyPool (IP rotation)
- Per-platform registration + login
- CredentialsStore (persist tokens)
- KillChainMatrix (run exploit per account)

Usage:
    factory = AccountFactory(platforms=["pagol", "4play", "4play_br"])
    results = factory.run_batch(count=10)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from src.auth.credentials import CredentialsStore
from src.factory.identity import Identity, IdentityGenerator
from src.factory.proxy import ProxyPool

log = logging.getLogger("betbonus.factory")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class AccountResult:
    """Result of registering + logging in one account on one platform."""
    identity: Identity
    platform: str
    success: bool = False
    token: str = ""
    refresh_token: str = ""
    error: str = ""
    registered: bool = False
    logged_in: bool = False
    http_status: int = 0


@dataclass
class FactoryResult:
    """Aggregate result of a batch run."""
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    accounts: list[AccountResult] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": f"{(self.succeeded / self.total * 100):.1f}%" if self.total else "N/A",
        }


# ---------------------------------------------------------------------------
# Platform registration configs
# ---------------------------------------------------------------------------

class PlatformConfig:
    """Registration/login endpoint config for a platform."""

    def __init__(
        self,
        name: str,
        register_url: str,
        login_url: str,
        register_method: str = "POST",
        login_method: str = "POST",
        register_content_type: str = "application/json",
        login_content_type: str = "application/json",
        register_payload_builder: Any = None,
        login_payload_builder: Any = None,
        token_extractor: Any = None,
        extra_headers: Optional[dict] = None,
    ):
        self.name = name
        self.register_url = register_url
        self.login_url = login_url
        self.register_method = register_method
        self.login_method = login_method
        self.register_content_type = register_content_type
        self.login_content_type = login_content_type
        self.register_payload_builder = register_payload_builder
        self.login_payload_builder = login_payload_builder
        self.token_extractor = token_extractor
        self.extra_headers = extra_headers or {}


def _default_token_extractor(data: dict) -> str:
    """Extract token from a generic JSON response."""
    if not isinstance(data, dict):
        return ""
    return (
        data.get("token")
        or data.get("access_token")
        or (data.get("data") or {}).get("token")
        or (data.get("data") or {}).get("access_token")
        or ""
    )


def _pagol_login_payload(identity: Identity) -> dict:
    return {
        "grant_type": "password",
        "username": identity.email,
        "password": identity.password,
    }


def _fourplay_login_payload(identity: Identity) -> dict:
    return {
        "email": identity.email,
        "password": identity.password,
        "cookie": False,
        "provider": "local",
    }


# ---------------------------------------------------------------------------
# Account Factory
# ---------------------------------------------------------------------------

class AccountFactory:
    """Orchestrates bulk account creation and kill-chain execution.

    Parameters:
        platforms: list of platform names to target (e.g. ["pagol", "4play", "4play_br"])
        credentials_store: optional CredentialsStore for persisting tokens
        proxy_pool: optional ProxyPool for IP rotation
        identity_generator: optional IdentityGenerator (created if not provided)
        register_delay: seconds to wait between registration attempts
        login_delay: seconds to wait between login attempts
    """

    # Default platform configs (extend as registration endpoints are discovered)
    DEFAULT_PLATFORMS: dict[str, PlatformConfig] = {
        "pagol": PlatformConfig(
            name="pagol",
            register_url="https://auth.pagol.luckygaming.com.br/oauth/token",
            login_url="https://auth.pagol.luckygaming.com.br/oauth/token",
            register_content_type="application/x-www-form-urlencoded",
            login_content_type="application/x-www-form-urlencoded",
            login_payload_builder=_pagol_login_payload,
            extra_headers={
                "Authorization": "Basic Y2xpZW50OjAxOFQ2c1VtVWxqZ2h0YkxkU1RzU21wM3QyZ0VQ",
            },
        ),
        "4play": PlatformConfig(
            name="4play",
            register_url="https://api.4play.game/api/v1/auth/register",
            login_url="https://api.4play.game/api/v1/auth/login",
            login_payload_builder=_fourplay_login_payload,
        ),
        "4play_br": PlatformConfig(
            name="4play_br",
            register_url="https://4play-api.4play.bet.br/api/client/register",
            login_url="https://4play-api.4play.bet.br/api/client/login",
        ),
    }

    def __init__(
        self,
        platforms: Optional[list[str]] = None,
        credentials_store: Optional[CredentialsStore] = None,
        proxy_pool: Optional[ProxyPool] = None,
        identity_generator: Optional[IdentityGenerator] = None,
        register_delay: float = 1.0,
        login_delay: float = 0.5,
        seed: Optional[int] = None,
    ):
        self.platforms = platforms or list(self.DEFAULT_PLATFORMS.keys())
        self.creds = credentials_store
        self.proxies = proxy_pool or ProxyPool()
        self.identities = identity_generator or IdentityGenerator(seed=seed)
        self.register_delay = register_delay
        self.login_delay = login_delay
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        })

    def _get_config(self, platform: str) -> Optional[PlatformConfig]:
        return self.DEFAULT_PLATFORMS.get(platform)

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_data: Optional[dict] = None,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        content_type: str = "application/json",
    ) -> tuple[int, Any]:
        """Make an HTTP request with optional proxy rotation."""
        hdrs = dict(self._session.headers)
        if headers:
            hdrs.update(headers)
        if content_type:
            hdrs["Content-Type"] = content_type

        proxy_url = self.proxies.next() if self.proxies else None
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

        try:
            resp = self._session.request(
                method,
                url,
                json=json_data,
                data=data,
                headers=hdrs,
                proxies=proxies,
                timeout=15,
            )
            try:
                body = resp.json()
            except Exception:
                body = resp.text[:500]
            return resp.status_code, body
        except requests.RequestException as e:
            return 0, str(e)

    def register_account(self, identity: Identity, platform: str) -> AccountResult:
        """Attempt to register an account on the given platform."""
        result = AccountResult(identity=identity, platform=platform)
        config = self._get_config(platform)
        if not config:
            result.error = f"Unknown platform: {platform}"
            return result

        # Build registration payload
        if config.register_payload_builder:
            payload = config.register_payload_builder(identity)
        else:
            payload = {
                "email": identity.email,
                "password": identity.password,
                "firstName": identity.first_name,
                "lastName": identity.last_name,
                "fullName": identity.full_name,
                "phone": identity.phone,
                "cpf": identity.cpf,
                "birthDate": identity.birth_date,
                "address": identity.address,
                "city": identity.city,
                "state": identity.state,
            }

        is_form = config.register_content_type == "application/x-www-form-urlencoded"
        status, body = self._request(
            config.register_method,
            config.register_url,
            json_data=None if is_form else payload,
            data=payload if is_form else None,
            headers=config.extra_headers,
            content_type=config.register_content_type,
        )
        result.http_status = status

        # Consider 200-201 as success; 409/422 may mean "already exists"
        if status in (200, 201):
            result.registered = True
            result.success = True
        elif status in (409, 422):
            # Account may already exist — try login
            result.registered = False
            result.error = f"Registration conflict (HTTP {status})"
        else:
            result.error = f"Registration failed (HTTP {status}): {str(body)[:200]}"

        return result

    def login_account(self, identity: Identity, platform: str) -> AccountResult:
        """Attempt to log in an account on the given platform."""
        result = AccountResult(identity=identity, platform=platform)
        config = self._get_config(platform)
        if not config:
            result.error = f"Unknown platform: {platform}"
            return result

        if config.login_payload_builder:
            payload = config.login_payload_builder(identity)
        else:
            payload = {
                "email": identity.email,
                "password": identity.password,
            }

        is_form = config.login_content_type == "application/x-www-form-urlencoded"
        status, body = self._request(
            config.login_method,
            config.login_url,
            json_data=None if is_form else payload,
            data=payload if is_form else None,
            headers=config.extra_headers,
            content_type=config.login_content_type,
        )
        result.http_status = status

        if status == 200:
            extractor = config.token_extractor or _default_token_extractor
            token = extractor(body) if isinstance(body, dict) else ""
            if token:
                result.token = token
                result.logged_in = True
                result.success = True
                # Persist to credentials store
                if self.creds:
                    label = f"{identity.email}@{platform}"
                    self.creds.save(
                        platform=f"{platform}:{identity.email}",
                        token=token,
                        email=identity.email,
                        label=label,
                    )
            else:
                result.error = "Login OK but no token in response"
        else:
            result.error = f"Login failed (HTTP {status}): {str(body)[:200]}"

        return result

    def create_account(self, identity: Identity, platform: str) -> AccountResult:
        """Register + login an account. Falls back to login-only if registration fails."""
        reg_result = self.register_account(identity, platform)
        if reg_result.registered:
            time.sleep(self.login_delay)
            login_result = self.login_account(identity, platform)
            if login_result.logged_in:
                return login_result
            # Registration succeeded but login failed
            reg_result.error = f"Registered but login failed: {login_result.error}"
            return reg_result

        # Registration failed or conflicted — try direct login
        time.sleep(self.login_delay)
        login_result = self.login_account(identity, platform)
        if login_result.logged_in:
            return login_result

        # Both failed
        reg_result.error = f"Register: {reg_result.error} | Login: {login_result.error}"
        return reg_result

    def run_batch(
        self,
        count: int,
        platforms: Optional[list[str]] = None,
        run_kill_chain: bool = False,
    ) -> FactoryResult:
        """Generate identities and create accounts across platforms.

        Args:
            count: number of identities to generate
            platforms: override the default platform list
            run_kill_chain: if True, run KillChainMatrix on each successful account

        Returns:
            FactoryResult with per-account details
        """
        targets = platforms or self.platforms
        identities = self.identities.generate_batch(count)
        result = FactoryResult(total=len(identities) * len(targets))
        result.accounts = []

        for identity in identities:
            for platform in targets:
                log.info("Creating account: %s @ %s", identity.email, platform)
                account_result = self.create_account(identity, platform)
                result.accounts.append(account_result)

                if account_result.success:
                    result.succeeded += 1
                    log.info("  ✓ Success: token=%s...", account_result.token[:20])

                    if run_kill_chain:
                        self._run_kill_chain_for_account(identity, platform, account_result)
                else:
                    result.failed += 1
                    log.warning("  ✗ Failed: %s", account_result.error)

                time.sleep(self.register_delay)

        log.info("Batch complete: %s", result.summary())
        return result

    def _run_kill_chain_for_account(
        self,
        identity: Identity,
        platform: str,
        account_result: AccountResult,
    ) -> None:
        """Run the kill chain matrix on a successfully created account."""
        try:
            from src.abuse.matrix import KillChainMatrix
            from src.scrapers.pagol_scraper import PagolScraper
            from src.scrapers.fourplay_scraper import FourPlayScraper
            from src.scrapers.fourplay_br_scraper import FourPlayBrScraper

            scraper = self._build_scraper(platform, account_result.token)
            if scraper is None:
                log.warning("  Could not build scraper for %s", platform)
                return

            matrix = KillChainMatrix(scraper, findings=None)
            report = matrix.run(
                confirm_real_withdraw=False,
                probe_high_ev=False,
                probe_slots=False,
                persist_findings=False,
            )
            account_result.error = f"Kill chain: {report.get('verdict', {}).get('dominant_blocker', 'unknown')}"
            log.info("  Kill chain verdict: %s", account_result.error)
        except Exception as e:
            log.warning("  Kill chain error: %s", e)

    def _build_scraper(self, platform: str, token: str) -> Optional[Any]:
        """Build a scraper instance for the given platform with the given token."""
        try:
            if platform == "pagol":
                from src.scrapers.pagol_scraper import PagolScraper
                return PagolScraper(delay=0, token=token)
            elif platform == "4play":
                from src.scrapers.fourplay_scraper import FourPlayScraper
                return FourPlayScraper(delay=0, token=token)
            elif platform == "4play_br":
                from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
                return FourPlayBrScraper(token=token)
        except Exception as e:
            log.warning("Failed to build scraper for %s: %s", platform, e)
        return None
