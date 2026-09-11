"""Trained spaCy NER path for bonus T&Cs (GAP 5).

Optional: loads a spaCy pipeline only when ``spacy`` is installed and
``BETBONUS_NLP_SPACY=1`` (default on) — otherwise ``is_available()`` is
False and callers fall back to the regex analyzer. A custom
``spacy-ner-bonus`` component (registered at import) extracts
wagering / free spins / expiry / min deposit / max bet / match % from
entity spans + local heuristics, so a plain ``en_core_web_sm`` model
works without retraining.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from src.models.bonus import BonusType
from src.nlp.analyzer import (
    CURRENCY_MAP,
    ExtractedBonusFields,
    NO_WAGERING_RE,
    _to_float,
)

_MODEL_CANDIDATES = ("en_core_web_trf", "en_core_web_sm", "en_core_web_md")
_WAGER_MULT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[xX×]")
_EXPIRY_RE = re.compile(
    r"(\d+)\s*(?:days?|hours?|d[ií]as?|horas?)", re.I
)
_MATCH_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_FREE_SPINS_RE = re.compile(
    r"(\d+)\s*(?:free\s*spins?|giros?\s*gr[aá]tis)", re.I
)
_TYPE_WORDS: dict[str, BonusType] = {
    "welcome": BonusType.WELCOME_BONUS,
    "no deposit": BonusType.NO_DEPOSIT,
    "cashback": BonusType.CASHBACK,
    "free spin": BonusType.FREE_SPINS,
    "free spins": BonusType.FREE_SPINS,
    "loyalty": BonusType.LOYALTY,
}


def _env_enabled() -> bool:
    return os.environ.get("BETBONUS_NLP_SPACY", "1").strip() != "0"


def _register_bonus_ner() -> None:
    """Register the custom bonus-terms NER component (idempotent)."""
    from spacy.language import Language

    @Language.component("spacy-ner-bonus")
    def _bonus_ner_factory(nlp, name="spacy-ner-bonus", assign_score=True):
        def _bonus_ner(doc):
            doc.ents = list(doc.ents)
            text = doc.text
            # Wagering multiple: "30x wagering" / "wagering 30x" / "30x rollover"
            for m in re.finditer(
                r"(?:wager(?:ing)?|rollover|playthrough|apuesta)\D{0,20}"
                r"(\d+(?:[.,]\d+)?)\s*[xX×]|[xX×]\s*(\d+(?:[.,]\d+)?)\s*"
                r"(?:wager|rollover|apuesta)",
                text,
                re.I,
            ):
                raw = m.group(1) or m.group(2)
                start, end = m.start(1), m.end(1)
                if m.group(1) is None:
                    start, end = m.start(2), m.end(2)
                char_start, char_end = doc.char_span(start, end)
                if char_start is not None:
                    doc.ents.append(char_start)
                    doc.ents[-1].label_ = "WAGERING_MULTIPLE"
                    doc.ents[-1].text = raw
            # No-wagering phrases → WAGERING_NONE
            if NO_WAGERING_RE.search(text):
                m = NO_WAGERING_RE.search(text)
                span = doc.char_span(m.start(), m.end())
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = "WAGERING_NONE"
            # Free spins
            for m in _FREE_SPINS_RE.finditer(text):
                span = doc.char_span(m.start(1), m.end(1))
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = "FREE_SPINS"
            # Expiry
            for m in _EXPIRY_RE.finditer(text):
                span = doc.char_span(m.start(1), m.end(1))
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = "EXPIRY"
            # Match percent
            for m in _MATCH_PCT_RE.finditer(text):
                span = doc.char_span(m.start(1), m.end(1))
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = "MATCH_PERCENT"
            # Money amounts (currency symbol / code + digits)
            for m in re.finditer(
                r"(?:₡|[$€£]|R\$|USD|EUR|GBP|BRL|CRC)\s*"
                r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)",
                text,
                re.I,
            ):
                span = doc.char_span(m.start(), m.end())
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = "MONEY"
            # Min deposit / max bet markers
            for m in re.finditer(
                r"min(?:imum)?\s*deposit|dep[oó]sito\s*m[ií]nimo|"
                r"max(?:imum)?\s*bet|apuesta\s*m[aá]xima|aposta\s*m[aá]xima",
                text,
                re.I,
            ):
                span = doc.char_span(m.start(), m.end())
                if span is not None:
                    doc.ents.append(span)
                    doc.ents[-1].label_ = (
                        "MIN_DEPOSIT" if "min" in m.group(0).lower()
                        else "MAX_BET"
                    )
            return doc

        return _bonus_ner_factory


def _load_pipeline():
    """Load a cached spaCy pipeline, or None when unavailable."""
    try:
        import spacy
    except ImportError:
        return None
    if not _env_enabled():
        return None
    _register_bonus_ner()
    try:
        import spacy
        from spacy.language import Language
        # Cache by model name so repeated loads are cheap.
        cache = getattr(_load_pipeline, "_cache", {})
        for name in _MODEL_CANDIDATES:
            if name in cache:
                return cache[name]
            try:
                nlp = spacy.load(name)
            except OSError:
                continue
            if "spacy-ner-bonus" not in nlp.component_names:
                nlp.add_pipe("spacy-ner-bonus", last=True)
            cache[name] = nlp
            _load_pipeline._cache = cache
            return nlp
    except Exception:  # noqa: BLE001
        return None
    return None


def is_available() -> bool:
    """True when a trained spaCy pipeline can be loaded."""
    return _load_pipeline() is not None


def extract_with_spacy(text: str) -> Optional[ExtractedBonusFields]:
    """Extract bonus fields with the trained NER path.

    Returns None when spaCy is unavailable (callers fall back to regex).
    """
    nlp = _load_pipeline()
    if nlp is None:
        return None
    try:
        doc = nlp(text)
    except Exception:  # noqa: BLE001
        return None

    fields = ExtractedBonusFields()

    for ent in doc.ents:
        label = ent.label_
        if label == "WAGERING_MULTIPLE":
            fields.wagering_multiple = _to_float(ent.text)
        elif label == "WAGERING_NONE":
            fields.wagering_multiple = 0.0
        elif label == "FREE_SPINS":
            try:
                fields.free_spins = int(float(ent.text))
            except ValueError:
                pass
        elif label == "EXPIRY":
            m = _EXPIRY_RE.search(ent.text)
            if m:
                value = int(m.group(1))
                if re.search(r"(?:hours?|horas?)", ent.text, re.I):
                    fields.expiry_hours = value
                    fields.expiry_days = (
                        max(1, value // 24) if value >= 24 else 0
                    )
                else:
                    fields.expiry_days = value
        elif label == "MATCH_PERCENT":
            fields.match_percent = _to_float(ent.text)
        elif label == "MONEY":
            value, currency = _split_money(ent.text)
            if value > fields.amount or fields.amount == 0:
                fields.amount = value
                fields.currency = currency

    # Min deposit / max bet: marker entity followed by a money entity.
    for i, ent in enumerate(doc.ents):
        if ent.label_ == "MIN_DEPOSIT":
            for nxt in doc.ents[i + 1 : i + 4]:
                if nxt.label_ == "MONEY":
                    fields.min_deposit = _split_money(nxt.text)[0]
                    break
        elif ent.label_ == "MAX_BET":
            for nxt in doc.ents[i + 1 : i + 4]:
                if nxt.label_ == "MONEY":
                    fields.max_bet_during_bonus = _split_money(nxt.text)[0]
                    break

    # Bonus type from text keywords (same rules as the regex path).
    fields.bonus_type = _identify_type(text)
    return fields


def _split_money(text: str) -> tuple[float, str]:
    m = re.search(
        r"(₡|[$€£]|R\$|USD|EUR|GBP|BRL|CRC)", text, re.I
    )
    symbol = m.group(1) if m else "$"
    currency = CURRENCY_MAP.get(symbol, CURRENCY_MAP.get(symbol.upper(), "USD"))
    digits = re.search(r"\d[\d.,]*", text)
    value = _to_float(digits.group(0)) if digits else 0.0
    return value, currency


def _identify_type(text: str) -> BonusType:
    t = text.lower()
    for key, bonus_type in _TYPE_WORDS.items():
        if key in t:
            return bonus_type
    if "%" in t and (
        "deposit" in t or "depósito" in t or "match" in t or "bono" in t
    ):
        return BonusType.DEPOSIT_MATCH
    return BonusType.UNKNOWN
