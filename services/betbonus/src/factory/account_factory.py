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

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from src.auth.credentials import CredentialsStore
from src.factory.identity import Identity, IdentityGenerator
from src.factory.proxy import ProxyPool
from src.factory.scheduler import TimingScheduler
from src.factory.tls import TLSFingerprintManager

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


@dataclass
class CampaignResult:
    """Result of a scheduled campaign (staggered multi-account operation)."""
    campaign_id: str
    accounts: list = field(default_factory=list)
    scheduler: Any = None
    pnl: Any = None
    behavior_profiles: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
        login_headers_builder: Any = None,
        register_headers_builder: Any = None,
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
        self.login_headers_builder = login_headers_builder
        self.register_headers_builder = register_headers_builder


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


# ---------------------------------------------------------------------------
# Pagol (pagol.bet.br) — HMAC token scheme + registration payload
# ---------------------------------------------------------------------------

_PAGOL_CLIENT_ID = "lucky-site"
_PAGOL_AUTH_TOKEN = "bHVja3ktc2l0ZTo4OWVidDNJYiFxRmJpelo="
_PAGOL_SECRET_KEY = "f04f7bf2-cd5b-4b69-a4f6-088a0e619512"
_PAGOL_API_URL = "https://api.pagol.luckygaming.com.br"
_PAGOL_LOGIN_URL = "https://auth.pagol.luckygaming.com.br"


def _pagol_generate_token(value: str, encrypt: bool) -> str:
    """Generate Pagol's HMAC-SHA256 token.

    - encrypt=True (credentials): payload = raw value
    - encrypt=False (X-Client-Token): payload = JSON.stringify({clientId: value, timestamp: now})
    Returns: base64(payload) + "." + hex(hmac_sha256(base64(payload), secret_key))
    """
    if not encrypt:
        value = json.dumps({"clientId": value, "timestamp": int(time.time() * 1000)}, separators=(",", ":"))
    b64 = base64.b64encode(value.encode()).decode()
    sig = hmac.new(_PAGOL_SECRET_KEY.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def _pagol_login_payload(identity: Identity) -> str:
    """Pagol OAuth2 password grant, form-urlencoded body with HMAC-encrypted credentials.

    Returns a pre-encoded string so the dot/equals characters in the HMAC
    tokens pass through verbatim (matches the SPA's form submission exactly).
    """
    from urllib.parse import urlencode
    return urlencode({
        "grant_type": "password",
        "username": _pagol_generate_token(identity.email, True),
        "password": _pagol_generate_token(identity.password, True),
        "clientId": _PAGOL_CLIENT_ID,
        "platform": "WEB",
        "lang": "pt-br",
    })


def _pagol_login_headers() -> dict:
    """Build per-request headers for Pagol OAuth login (X-Client-Token is time-based)."""
    return {
        "Authorization": f"Basic {_PAGOL_AUTH_TOKEN}",
        "X-Client-Token": _pagol_generate_token("/oauth/token", False),
        "Akamai-BM-Telemetry": "",
        "Origin": "https://pagol.bet.br",
        "Referer": "https://pagol.bet.br/",
    }


def _pagol_register_headers() -> dict:
    """Build per-request headers for Pagol registration.

    For a NEW user, the SPA sends Authorization: Bearer (empty token) plus
    X-Client-Token (HMAC of the endpoint path) and Akamai-BM-Telemetry.
    """
    return {
        "Authorization": "Bearer ",
        "X-Client-Token": _pagol_generate_token("/user/register.do", False),
        "Akamai-BM-Telemetry": "",
        "Origin": "https://pagol.bet.br",
        "Referer": "https://pagol.bet.br/",
    }


def _pagol_register_payload(identity: Identity) -> dict:
    """Pagol /user/register.do JSON body matching the SPA's createBody().

    Key server requirements discovered via API probing:
    - language: "pt" (enum LanguageCode value, NOT "pt-br")
    - birthDate: dd/MM/yyyy format (e.g. "23/03/1994")
    - documentStatus: "VALID" (empty string → 400)
    - socialPlatform: must be omitted (any value → 400)
    - cellphoneCountry: numeric country code (55 for Brazil)
    """
    phone_digits = "".join(c for c in identity.phone if c.isdigit())
    # phone format: (DD) 9XXXX-XXXX → DDD=2 digits, number=9 digits
    ddd = phone_digits[:2]
    number = phone_digits[2:]
    cpf_digits = "".join(c for c in identity.cpf if c.isdigit())
    username = identity.email.split("@")[0]
    # Convert YYYY-MM-DD to dd/MM/yyyy for the server
    parts = identity.birth_date.split("-")
    birth_ddmmyyyy = f"{parts[2]}/{parts[1]}/{parts[0]}"
    return {
        "fullname": identity.full_name,
        "username": username,
        "password": identity.password,
        "email": identity.email,
        "cellphone": number,
        "cellphoneCountry": 55,
        "language": "pt",
        "currency": "BRL",
        "promocode": "",
        "newsletter": False,
        "userPlatform": "WEB",
        "socialId": "",
        "btagCode": "",
        "deviceKey": "",
        "deviceId": "",
        "birthDate": birth_ddmmyyyy,
        "gender": identity.gender,
        "zipCode": "12345678",
        "documentNumber": cpf_digits,
        "city": identity.city,
        "nationality": "BR",
        "cafRegistrationId": "",
        "address": identity.address,
        "neighborhood": "Centro",
        "apartamentNumber": "",
        "state": identity.state,
        "complement": "",
        "proofAddress": "",
        "mailingAddress": "",
        "pixType": "CPF",
        "pixKey": cpf_digits,
        "documentStatus": "VALID",
        "latitude": "-23.5505",
        "longitude": "-46.6333",
        "transfer": False,
        "isPep": False,
        "pldFt": False,
        "affilkaTag": "",
        "affiliateId": "",
        "userEventAnalytics": {
            "fbclid": "",
            "gclid": "",
            "refCode": "",
            "utmSource": "",
            "utmCampaign": "",
            "utmContent": "",
        },
        "invitedTag": "",
        "authToken": _PAGOL_AUTH_TOKEN,
    }


def _fourplay_login_payload(identity: Identity) -> dict:
    return {
        "email": identity.email,
        "password": identity.password,
        "cookie": False,
        "provider": "local",
    }


# ---------------------------------------------------------------------------
# 4play_br (4play.bet.br) — ASP.NET backend with RSA-encrypted login
# ---------------------------------------------------------------------------

_FOURPLAY_BR_RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxDV6Tkh5noY4NWUd5G3q
mdLkhBCRwwG06buiCc34Xyshtc8eRMaLZarHeQpEkPk43f7Xo7UhOekqQ1+/JlZO
rCKRUb8VPdLv/gA9lxzDAJDuSTN8RY0BBJlwNjrP3nrDLIfxAe5OZXxgdwvSi5Rx
nghWaiM7qtrcaAKcnZnoNrHXvouw9CbLEJa92RJjKIUE94GbFozDSM62CokXrKC9
RgcwZfLQijzlgKM90pjLjAlw1Iz/IN3g5k+TqrbHX7zo8I85MIn/1yRyUIGMT3BU
MiPKRkCqVZ1NGPLLsuz4vCe/wA9dmhZxrEAECLEFp6/9PoT9abcIxIYJpV1PhxeG
1wIDAQAB
-----END PUBLIC KEY-----"""


def _fourplay_br_encrypt(data: dict) -> str:
    """RSA-encrypt a dict to base64 (OAEP-SHA1), matching the JS bundle's Li() function."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        public_key = serialization.load_pem_public_key(_FOURPLAY_BR_RSA_PUBLIC_KEY.encode())
        plaintext = json.dumps(data, separators=(",", ":"))
        encrypted = public_key.encrypt(
            plaintext.encode(),
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode()
    except ImportError:
        # Fallback: return plaintext JSON if cryptography lib is missing
        return json.dumps(data, separators=(",", ":"))


def _fourplay_br_register_payload(identity: Identity) -> dict:
    """4play.br (ASP.NET) expects CPF-based registration with Turnstile captcha.

    Full flow: verify-cpf-number → register-with-cpf-number → flow-post-registration.
    The register endpoint requires a valid Cloudflare Turnstile token in reCaptcha.
    """
    cpf_digits = identity.cpf.replace(".", "").replace("-", "")
    return {
        "email": identity.email,
        "password": identity.password,
        "document": cpf_digits,
        "fullName": identity.full_name,
        "acceptTermsConditions": True,
        "loginType": 0,
        "token": "",
        "reCaptcha": "",
        "offers": False,
    }


def _fourplay_br_login_payload(identity: Identity) -> dict:
    """4play.br login requires RSA-encrypted credentials (OAEP-SHA1)."""
    encrypted = _fourplay_br_encrypt({
        "clientIdentifier": identity.email,
        "password": identity.password,
        "rememberMe": False,
        "loginType": 0,
    })
    return {
        "data": encrypted,
        "reCaptcha": "",
        "idToken": None,
        "loginType": 0,
    }


def _fourplay_register_payload(identity: Identity) -> dict:
    """4play Go backend expects a Costa Rican identity with E.164 phone,
    RFC3339 birthday, and structured auth.Address with zip."""
    # Convert phone to E.164: strip formatting, prefix +50 (Costa Rica)
    phone_digits = "".join(c for c in identity.phone if c.isdigit())
    if phone_digits.startswith("50"):
        e164 = f"+{phone_digits}"
    else:
        e164 = f"+50{phone_digits[-8:]}"
    # Convert birthday to RFC3339
    birthday = f"{identity.birth_date}T00:00:00Z"
    # Map gender
    gender = "male" if identity.gender == "M" else "female"
    # Costa Rican document (Cedula): "01" + 7 random digits (national cedula)
    cpf_digits = "".join(c for c in identity.cpf if c.isdigit())
    doc_digits = "01" + cpf_digits[2:9]
    return {
        "email": identity.email,
        "password": identity.password,
        "firstName": identity.first_name,
        "lastName": identity.last_name,
        "fullName": identity.full_name,
        "phone": e164,
        "document": doc_digits,
        "birthday": birthday,
        "gender": gender,
        "acceptTerms": True,
        "acceptDataTreatment": True,
        "address": {
            "street": identity.address,
            "city": identity.city,
            "state": identity.state,
            "country": "CR",
            "zip": "10101",
        },
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
            register_url=f"{_PAGOL_API_URL}/user/register.do",
            login_url=f"{_PAGOL_LOGIN_URL}/oauth/token",
            register_content_type="application/json",
            login_content_type="application/x-www-form-urlencoded",
            register_payload_builder=_pagol_register_payload,
            login_payload_builder=_pagol_login_payload,
            extra_headers={
                "Origin": "https://pagol.bet.br",
                "Referer": "https://pagol.bet.br/",
            },
            login_headers_builder=_pagol_login_headers,
            register_headers_builder=_pagol_register_headers,
        ),
        "4play": PlatformConfig(
            name="4play",
            register_url="https://api.4play.game/api/v1/auth/register",
            login_url="https://api.4play.game/api/v1/auth/login",
            register_payload_builder=_fourplay_register_payload,
            login_payload_builder=_fourplay_login_payload,
        ),
        "4play_br": PlatformConfig(
            name="4play_br",
            register_url="https://4play-api.4play.bet.br/api/registration/register-with-cpf-number",
            login_url="https://4play-api.4play.bet.br/api/registration/login-client",
            register_payload_builder=_fourplay_br_register_payload,
            login_payload_builder=_fourplay_br_login_payload,
            extra_headers={"Origin": "https://4play.bet.br", "Referer": "https://4play.bet.br/"},
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

    # Aliases → canonical factory platform keys
    _PLATFORM_ALIASES: dict[str, str] = {
        "pagol_bet_br": "pagol",
        "pagol.bet.br": "pagol",
        "4play_bet_br": "4play_br",
        "4play.bet.br": "4play_br",
        "4play_game": "4play",
        "4play.game": "4play",
    }

    def _get_config(self, platform: str) -> Optional[PlatformConfig]:
        canonical = self._PLATFORM_ALIASES.get(platform, platform)
        return self.DEFAULT_PLATFORMS.get(canonical)

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
        # Use dynamic headers builder if available (e.g. time-based X-Client-Token)
        if config.register_headers_builder:
            reg_headers = config.register_headers_builder()
        else:
            reg_headers = config.extra_headers
        status, body = self._request(
            config.register_method,
            config.register_url,
            json_data=None if is_form else payload,
            data=payload if is_form else None,
            headers=reg_headers,
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
        # Use dynamic headers builder (e.g. Pagol X-Client-Token) when available
        if config.login_headers_builder:
            hdrs = config.login_headers_builder()
        else:
            hdrs = config.extra_headers
        # Payload builders may return a pre-encoded string (e.g. Pagol's
        # form body with HMAC tokens) — send it verbatim.
        if isinstance(payload, str):
            status, body = self._request(
                config.login_method,
                config.login_url,
                data=payload,
                headers=hdrs,
                content_type=config.login_content_type,
            )
        else:
            status, body = self._request(
                config.login_method,
                config.login_url,
                json_data=None if is_form else payload,
                data=payload if is_form else None,
                headers=hdrs,
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

    # ------------------------------------------------------------------
    # Campaign support
    # ------------------------------------------------------------------

    def run_campaign(
        self,
        count: int,
        platforms: list[str],
        *,
        stagger_minutes: int = 10,
        use_behavior: bool = True,
    ) -> "CampaignResult":
        """Generate a staggered multi-account campaign.

        1. Generates N identities
        2. Creates BehavioralFingerprint profiles for each
        3. Schedules registration events (staggered)
        4. Returns a CampaignResult with all scheduled info

        Args:
            count: number of accounts to create
            platforms: list of platform names to target
            stagger_minutes: minimum gap between registration events
            use_behavior: if True, attach behavioral fingerprint profiles

        Returns:
            CampaignResult with scheduled accounts and profiles
        """
        from uuid import uuid4

        campaign_id = f"camp-{uuid4().hex[:8]}"
        log.info("Starting campaign %s: %d accounts on %s", campaign_id, count, platforms)

        # 1. Generate identities
        identities = self.identities.generate_batch(count)
        log.info("Generated %d identities", len(identities))

        # 2. Create behavioral fingerprint profiles
        behavior_profiles: dict[str, Any] = {}
        if use_behavior:
            try:
                from src.factory.behavior import BehavioralFingerprint
                for ident in identities:
                    account_key = f"{ident.email}@{platforms[0]}"
                    behavior_profiles[account_key] = BehavioralFingerprint(
                        account_id=account_key,
                        seed=self.identities.rng.randint(0, 2**32 - 1),
                    )
                log.info("Created %d behavioral profiles", len(behavior_profiles))
            except ImportError:
                log.warning(
                    "BehavioralFingerprint not available (src.abuse.behavior) — "
                    "skipping behavior profiles"
                )
            except Exception as e:
                log.warning("Failed to create behavior profiles: %s", e)

        # 3. Schedule registration events
        scheduler = TimingScheduler(
            min_gap_minutes=stagger_minutes,
            seed=self.identities.rng.randint(0, 2**32 - 1),
        )
        account_ids = [
            f"{ident.email}@{platforms[0]}" for ident in identities
        ]
        reg_events = scheduler.schedule_registration(account_ids)
        log.info(
            "Scheduled %d registration events (first: %s, last: %s)",
            len(reg_events),
            reg_events[0].scheduled_at.isoformat() if reg_events else "N/A",
            reg_events[-1].scheduled_at.isoformat() if reg_events else "N/A",
        )

        # 4. Try to create PnL tracker
        pnl = None
        try:
            from src.factory.pnl import CampaignPnL
            pnl = CampaignPnL(campaign_id=campaign_id)
            log.info("Created PnL tracker for campaign")
        except ImportError:
            log.info("PnL tracker not available (src.factory.pnl) — skipping")
        except Exception as e:
            log.warning("Failed to create PnL tracker: %s", e)

        # Build account list for the result
        accounts: list[dict] = []
        for ident, event in zip(identities, reg_events):
            accounts.append({
                "identity": ident,
                "email": ident.email,
                "platforms": platforms,
                "scheduled_at": event.scheduled_at,
                "event_id": event.event_id,
                "behavior_profile": behavior_profiles.get(
                    f"{ident.email}@{platforms[0]}"
                ),
            })

        result = CampaignResult(
            campaign_id=campaign_id,
            accounts=accounts,
            scheduler=scheduler,
            pnl=pnl,
            behavior_profiles=behavior_profiles,
        )

        log.info(
            "Campaign %s ready: %d accounts, timeline=%s",
            campaign_id, len(accounts), scheduler.campaign_timeline(),
        )
        return result
