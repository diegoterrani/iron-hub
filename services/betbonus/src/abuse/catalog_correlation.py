"""Correlação de catálogo (IP/device/fingerprint) — só texto das ofertas.

Não cria contas. Não coleta fingerprint de jogadores. Serve para decidir se
P0/P1 de engenharia se justifica por exploração em escala.
"""

from __future__ import annotations

import re
from typing import Any

_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ip", (r"\bip\b", "endereço ip", "same ip", "mesmo ip", "ip address")),
    (
        "device",
        ("device fingerprint", "fingerprint", "device-id", "dispositivo", "device id"),
    ),
    (
        "identity",
        (
            r"\bcpf\b",
            "kyc",
            "one account",
            "uma conta",
            "per customer",
            "por jogador",
            "por cpf",
        ),
    ),
    (
        "multi_account",
        (
            "multi-account",
            "multi account",
            "múltiplas contas",
            "multiplas contas",
            "alt account",
            "contas múltiplas",
        ),
    ),
)


def _blob(offer: dict[str, Any]) -> str:
    parts = [
        offer.get("title"),
        offer.get("raw_text"),
        offer.get("terms_url"),
        offer.get("bonus_type"),
        " ".join(str(x) for x in (offer.get("game_restrictions") or [])),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def scan_offer_catalog(offers: list[dict[str, Any]]) -> dict[str, Any]:
    hits: dict[str, list[str]] = {k: [] for k, _ in _MARKERS}
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        text = _blob(offer)
        oid = str(offer.get("id") or offer.get("title") or "")[:48]
        for key, needles in _MARKERS:
            for needle in needles:
                if re.search(needle, text, re.I):
                    if oid not in hits[key]:
                        hits[key].append(oid)
                    break
    any_control = any(hits[k] for k in hits)
    return {
        "scanned": len(offers),
        "hits": hits,
        "catalog_exposes_scale_controls": any_control,
        "scale_justifies_p0": False,
        "note": (
            "Sem campos de fingerprint/IP na API de ofertas, correlação de multi-accounting "
            "não é possível neste catálogo. P0/P1 de engenharia permanece hipótese até lab "
            "com N contas e sinais de device/IP do operador — não deste harness."
            if not any_control
            else "Catálogo menciona controle de IP/device/identidade no texto; validar no BO antes de P0."
        ),
    }
