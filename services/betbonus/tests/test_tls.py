"""Tests for TLSFingerprintManager (Phase 3)."""

from __future__ import annotations

import pytest

from src.factory.tls import BrowserFingerprint, TLSFingerprintManager


def test_fingerprint_deterministic_per_account():
    mgr = TLSFingerprintManager()
    fp1 = mgr.generate_fingerprint("acct-1")
    fp2 = mgr.generate_fingerprint("acct-1")
    assert fp1.user_agent == fp2.user_agent
    assert fp1.sec_ch_ua == fp2.sec_ch_ua
    assert fp1.sec_ch_ua_platform == fp2.sec_ch_ua_platform
    assert fp1.accept_language == fp2.accept_language


def test_fingerprint_unique_per_account():
    mgr = TLSFingerprintManager()
    uas = {mgr.generate_fingerprint(f"acct-{i}").user_agent for i in range(15)}
    # With a 26-entry pool, 15 accounts should yield several distinct UAs
    assert len(uas) >= 3


def test_headers_dict_structure():
    mgr = TLSFingerprintManager()
    fp = mgr.generate_fingerprint("acct-1")
    headers = mgr.headers_dict(fp)
    assert headers["User-Agent"] == fp.user_agent
    assert "Accept-Language" in headers
    assert "Sec-Ch-Ua" in headers
    assert "Sec-Ch-Ua-Platform" in headers
    assert "Sec-Fetch-Dest" in headers
    assert "Sec-Fetch-Mode" in headers
    assert "Upgrade-Insecure-Requests" in headers
    assert "Connection" in headers
    assert "Accept" in headers
    assert headers["Sec-Ch-Ua-Mobile"] == "?0"


def test_headers_consistent_with_fingerprint():
    mgr = TLSFingerprintManager()
    fp = mgr.generate_fingerprint("acct-1")
    h1 = mgr.headers_dict(fp)
    h2 = mgr.headers_dict(fp)
    assert h1 == h2


def test_fingerprint_chrome_version():
    mgr = TLSFingerprintManager()
    import re
    fp = mgr.generate_fingerprint("acct-1")
    match = re.search(r"Chrome/(\d+)\.", fp.user_agent)
    assert match is not None
    assert int(match.group(1)) >= 120


def test_sec_ch_ua_matches_ua():
    mgr = TLSFingerprintManager()
    import re
    for i in range(10):
        fp = mgr.generate_fingerprint(f"acct-{i}")
        ua_major = re.search(r"Chrome/(\d+)\.", fp.user_agent).group(1)
        sec_major = re.search(r'Chromium;v="(\d+)"', fp.sec_ch_ua).group(1)
        assert ua_major == sec_major


def test_platform_consistency():
    mgr = TLSFingerprintManager()
    import re
    for i in range(10):
        fp = mgr.generate_fingerprint(f"acct-{i}")
        if "Windows" in fp.user_agent:
            assert fp.sec_ch_ua_platform == '"Windows"'
        elif "Macintosh" in fp.user_agent:
            assert fp.sec_ch_ua_platform == '"macOS"'
        else:
            assert fp.sec_ch_ua_platform == '"Linux"'


def test_validate_fingerprint_passes():
    mgr = TLSFingerprintManager()
    for i in range(10):
        fp = mgr.generate_fingerprint(f"acct-{i}")
        assert mgr.validate_fingerprint(fp) is True


def test_validate_fingerprint_rejects_old_chrome():
    mgr = TLSFingerprintManager()
    fp = BrowserFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0",
        accept_language="pt-BR",
        sec_ch_ua='Chromium;v="110", Google Chrome;v="110", Not-A.Brand;v="99"',
        sec_ch_ua_platform='"Windows"',
    )
    assert mgr.validate_fingerprint(fp) is False


def test_validate_fingerprint_rejects_empty_lang():
    mgr = TLSFingerprintManager()
    fp = BrowserFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        accept_language="",
        sec_ch_ua='Chromium;v="120", Google Chrome;v="120", Not-A.Brand;v="99"',
        sec_ch_ua_platform='"Windows"',
    )
    assert mgr.validate_fingerprint(fp) is False


def test_user_agent_pool():
    mgr = TLSFingerprintManager()
    pool = mgr.user_agent_pool()
    assert len(pool) >= 20
    assert all("Chrome/" in ua for ua in pool)


def test_create_session_returns_session():
    mgr = TLSFingerprintManager()
    session = mgr.create_session("acct-1")
    assert session is not None
    assert "User-Agent" in session.headers
