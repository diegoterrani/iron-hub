"""Tests for the account factory / multi-account scale layer."""

import pytest
from unittest.mock import patch, MagicMock

from src.factory.identity import IdentityGenerator, Identity, generate_cpf
from src.factory.proxy import ProxyPool, ProxyEntry
from src.factory.account_factory import (
    AccountFactory,
    AccountResult,
    FactoryResult,
    PlatformConfig,
)


# ---------------------------------------------------------------------------
# Identity generator
# ---------------------------------------------------------------------------

class TestIdentityGenerator:
    def test_generate_returns_identity(self):
        gen = IdentityGenerator(seed=42)
        ident = gen.generate()
        assert isinstance(ident, Identity)
        assert ident.full_name
        assert "@" in ident.email
        assert ident.cpf
        assert ident.phone
        assert ident.password
        assert ident.cnh
        assert ident.birth_date
        assert ident.state

    def test_cpf_valid_format(self):
        gen = IdentityGenerator(seed=1)
        for _ in range(50):
            ident = gen.generate()
            # CPF format: XXX.XXX.XXX-XX
            digits = ident.cpf.replace(".", "").replace("-", "")
            assert len(digits) == 11
            assert digits.isdigit()

    def test_cpf_check_digits(self):
        """Verify generated CPFs pass the standard check-digit validation."""
        gen = IdentityGenerator(seed=99)
        for _ in range(30):
            cpf = gen.generate().cpf
            digits = cpf.replace(".", "").replace("-", "")
            d1 = digits[9]
            d2 = digits[10]
            # Recompute d1
            w = [10, 9, 8, 7, 6, 5, 4, 3, 2]
            s = sum(int(d) * wi for d, wi in zip(digits[:9], w))
            r = s % 11
            expected_d1 = "0" if r < 2 else str(11 - r)
            assert d1 == expected_d1, f"CPF {cpf}: expected d1={expected_d1}, got {d1}"

    def test_cnh_valid_format(self):
        gen = IdentityGenerator(seed=7)
        for _ in range(20):
            cnh = gen.generate().cnh
            assert len(cnh) == 9
            assert cnh[:8].isdigit()
            assert cnh[8].isalpha()

    def test_batch_uniqueness(self):
        gen = IdentityGenerator(seed=123)
        batch = gen.generate_batch(20)
        emails = [i.email for i in batch]
        assert len(set(emails)) == len(emails), "Duplicate emails in batch"

    def test_deterministic_with_seed(self):
        gen1 = IdentityGenerator(seed=42)
        gen2 = IdentityGenerator(seed=42)
        i1 = gen1.generate()
        i2 = gen2.generate()
        assert i1.email == i2.email
        assert i1.cpf == i2.cpf
        assert i1.full_name == i2.full_name

    def test_phone_format(self):
        import re
        gen = IdentityGenerator(seed=5)
        for _ in range(10):
            phone = gen.generate().phone
            # Format: (DD) 9XXXX-XXXX or (DDD) 9XXXX-XXXX
            assert re.match(r"^\(\d{2,3}\) 9\d{4}-\d{4}$", phone), f"Bad phone format: {phone}"

    def test_to_dict(self):
        gen = IdentityGenerator(seed=1)
        ident = gen.generate()
        d = ident.to_dict()
        assert d["email"] == ident.email
        assert d["cpf"] == ident.cpf
        assert "password" in d


# ---------------------------------------------------------------------------
# Proxy pool
# ---------------------------------------------------------------------------

class TestProxyPool:
    def test_empty_pool_returns_none(self):
        pool = ProxyPool()
        assert pool.next() is None
        assert pool.random() is None
        assert pool.requests_proxies() is None
        assert not pool

    def test_round_robin(self):
        pool = ProxyPool(["http://proxy1:8080", "http://proxy2:8080"])
        assert len(pool) == 2
        assert pool.next() == "http://proxy1:8080"
        assert pool.next() == "http://proxy2:8080"
        assert pool.next() == "http://proxy1:8080"  # wraps around

    def test_parse_with_auth(self):
        entry = ProxyEntry.parse("http://user:pass@10.0.0.1:3128")
        assert entry.scheme == "http"
        assert entry.username == "user"
        assert entry.password == "pass"
        assert entry.host == "10.0.0.1"
        assert entry.port == 3128
        assert entry.to_url() == "http://user:pass@10.0.0.1:3128"

    def test_parse_simple(self):
        entry = ProxyEntry.parse("192.168.1.1:8080")
        assert entry.host == "192.168.1.1"
        assert entry.port == 8080
        assert entry.scheme == "http"

    def test_parse_https(self):
        entry = ProxyEntry.parse("https://proxy.example.com:443")
        assert entry.scheme == "https"
        assert entry.host == "proxy.example.com"
        assert entry.port == 443

    def test_from_env(self):
        with patch.dict("os.environ", {"BETBONUS_PROXIES": "http://a:1,http://b:2"}):
            pool = ProxyPool.from_env()
            assert len(pool) == 2

    def test_requests_proxies_dict(self):
        pool = ProxyPool(["http://p:8080"])
        d = pool.requests_proxies()
        assert d == {"http": "http://p:8080", "https": "http://p:8080"}


# ---------------------------------------------------------------------------
# Account Factory
# ---------------------------------------------------------------------------

class TestAccountFactory:
    def _make_factory(self, **kwargs):
        return AccountFactory(
            platforms=["pagol", "4play", "4play_br"],
            identity_generator=IdentityGenerator(seed=42),
            proxy_pool=ProxyPool([]),
            **kwargs,
        )

    def test_default_platforms(self):
        f = self._make_factory()
        assert "pagol" in f.platforms
        assert "4play" in f.platforms
        assert "4play_br" in f.platforms

    def test_register_account_unknown_platform(self):
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.register_account(ident, "unknown_platform")
        assert not result.success
        assert "Unknown platform" in result.error

    @patch.object(AccountFactory, "_request")
    def test_register_success(self, mock_req):
        mock_req.return_value = (200, {"message": "created"})
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.register_account(ident, "4play")
        assert result.success
        assert result.registered
        assert result.http_status == 200

    @patch.object(AccountFactory, "_request")
    def test_register_conflict(self, mock_req):
        mock_req.return_value = (409, {"error": "exists"})
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.register_account(ident, "4play")
        assert not result.registered
        assert "conflict" in result.error.lower()

    @patch.object(AccountFactory, "_request")
    def test_login_success(self, mock_req):
        mock_req.return_value = (200, {"token": "abc123"})
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.login_account(ident, "4play")
        assert result.logged_in
        assert result.token == "abc123"
        assert result.success

    @patch.object(AccountFactory, "_request")
    def test_login_no_token(self, mock_req):
        mock_req.return_value = (200, {"message": "ok"})
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.login_account(ident, "4play")
        assert not result.logged_in
        assert "no token" in result.error.lower()

    @patch.object(AccountFactory, "_request")
    def test_login_failure(self, mock_req):
        mock_req.return_value = (401, {"error": "invalid"})
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.login_account(ident, "4play")
        assert not result.logged_in
        assert "401" in result.error

    @patch.object(AccountFactory, "register_account")
    @patch.object(AccountFactory, "login_account")
    def test_create_account_full_flow(self, mock_login, mock_reg):
        mock_reg.return_value = AccountResult(
            identity=IdentityGenerator(seed=1).generate(),
            platform="4play",
            success=True,
            registered=True,
        )
        mock_login.return_value = AccountResult(
            identity=IdentityGenerator(seed=1).generate(),
            platform="4play",
            success=True,
            logged_in=True,
            token="tok123",
        )
        f = self._make_factory()
        ident = IdentityGenerator(seed=1).generate()
        result = f.create_account(ident, "4play")
        assert result.success
        assert result.token == "tok123"

    def test_run_batch_structure(self):
        f = self._make_factory(register_delay=0, login_delay=0)
        with patch.object(f, "create_account") as mock_create:
            mock_create.return_value = AccountResult(
                identity=IdentityGenerator(seed=1).generate(),
                platform="pagol",
                success=True,
            )
            result = f.run_batch(count=3, platforms=["pagol"])
            assert result.total == 3
            assert result.succeeded == 3
            assert len(result.accounts) == 3

    def test_factory_result_summary(self):
        fr = FactoryResult(total=10, succeeded=8, failed=2)
        s = fr.summary()
        assert s["total"] == 10
        assert s["succeeded"] == 8
        assert s["failed"] == 2
        assert s["success_rate"] == "80.0%"

    def test_factory_result_empty_summary(self):
        fr = FactoryResult()
        s = fr.summary()
        assert s["success_rate"] == "N/A"


# ---------------------------------------------------------------------------
# Integration: identity → factory flow
# ---------------------------------------------------------------------------

class TestFactoryIntegration:
    def test_identity_fields_for_registration(self):
        """Verify Identity has all fields needed for platform registration."""
        gen = IdentityGenerator(seed=42)
        ident = gen.generate()
        required = ["email", "password", "full_name", "first_name", "last_name",
                     "phone", "cpf", "birth_date", "address", "city", "state"]
        for field_name in required:
            assert getattr(ident, field_name, ""), f"Missing field: {field_name}"

    def test_pagol_login_payload(self):
        from src.factory.account_factory import _pagol_login_payload
        gen = IdentityGenerator(seed=1)
        ident = gen.generate()
        payload = _pagol_login_payload(ident)
        assert payload["grant_type"] == "password"
        assert payload["username"] == ident.email
        assert payload["password"] == ident.password

    def test_fourplay_login_payload(self):
        from src.factory.account_factory import _fourplay_login_payload
        gen = IdentityGenerator(seed=1)
        ident = gen.generate()
        payload = _fourplay_login_payload(ident)
        assert payload["email"] == ident.email
        assert payload["password"] == ident.password
        assert payload["provider"] == "local"
