from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from src.models.bonus import BonusType


WAGERING_RE = re.compile(
    r"(?:wager(?:ing)?|rollover|playthrough|requisito\s+de\s+apuesta|"
    r"apostas?\s+m[ií]nimas?|apuesta(?:s)?(?:\s+m[ií]nima(?:s)?)?)"
    r"[^\d]{0,40}(\d+(?:[.,]\d+)?)\s*[xX×]",
    re.IGNORECASE,
)
WAGERING_SHORT_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*[xX×]\s*(?:wager|rollover|apuesta|requisito)?\b",
    re.I,
)
NO_WAGERING_RE = re.compile(
    r"(?:sem\s+rollover|sem\s+requisito(?:\s+de\s+aposta)?|no\s+wager(?:ing)?|"
    r"zero\s+wager(?:ing)?|wager(?:ing)?\s*free|rollover\s*(?:zero|0)|"
    r"0\s*[xX×]\s*(?:wager|rollover|aposta)?)",
    re.IGNORECASE,
)

AMOUNT_PATTERNS = [
    re.compile(r"(?:up\s+to|hasta|at[eé]|até)\s*(₡|[$€£]|R\$)\s*(\d+(?:[.,]\d+)?)", re.I),
    re.compile(r"(₡|[$€£]|R\$)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)", re.I),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*(USD|EUR|GBP|BRL|CRC|\$|€|£|₡)", re.I),
]

MATCH_PERCENT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*%\s*(?:match|deposit|dep[oó]sito|b[oô]nus|bono)?",
    re.I,
)
FREE_SPINS_RE = re.compile(
    r"(\d+)\s*(?:free\s*spins?|giros?\s*gr[aá]tis|giros?(?:\s*gratis)?)",
    re.I,
)
MIN_DEPOSIT_RE = re.compile(
    r"(?:min(?:imum)?\s*deposit|dep[oó]sito\s*m[ií]nimo)[^\d₡$€£]{0,20}"
    r"(₡|[$€£]|R\$)?\s*(\d+(?:[.,]\d+)?)",
    re.I,
)
MAX_BET_RE = re.compile(
    r"(?:max(?:imum)?\s*bet|apuesta\s*m[aá]xima|aposta\s*m[aá]xima)[^\d₡$€£]{0,20}"
    r"(₡|[$€£]|R\$)?\s*(\d+(?:[.,]\d+)?)",
    re.I,
)
EXPIRY_DAY_RE = re.compile(r"(\d+)\s*(?:days?|d[ií]as?)", re.I)
EXPIRY_HOUR_RE = re.compile(r"(\d+)\s*(?:hours?|horas?)", re.I)

CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "R$": "BRL",
    "₡": "CRC",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "BRL": "BRL",
    "CRC": "CRC",
}

GAME_KEYWORDS = [
    "slots",
    "tragamonedas",
    "roulette",
    "ruleta",
    "blackjack",
    "baccarat",
    "sports",
    "deportes",
    "live casino",
    "casino en vivo",
    "casino",
    "table games",
    "crash",
    "poker",
]


def _to_float(value: str) -> float:
    cleaned = value.strip()
    # Costa Rica / LATAM thousands: 3.000.000 or 3,000,000
    if cleaned.count(".") > 1 and "," not in cleaned:
        cleaned = cleaned.replace(".", "")
    elif cleaned.count(",") > 1 and "." not in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


@dataclass
class ExtractedBonusFields:
    bonus_type: BonusType = BonusType.UNKNOWN
    amount: float = 0.0
    currency: str = "USD"
    match_percent: Optional[float] = None
    free_spins: Optional[int] = None
    wagering_multiple: float = 30.0
    min_deposit: float = 0.0
    max_bet_during_bonus: Optional[float] = None
    expiry_days: int = 30
    expiry_hours: Optional[int] = None
    game_restrictions: list[str] = field(default_factory=list)


class BonusNLPAnalyzer:
    """Lightweight regex/NLP extractor for bonus T&Cs (spaCy optional later)."""

    def identify_type(self, text: str) -> BonusType:
        t = text.lower()
        if (
            "welcome" in t
            or "bienvenida" in t
            or "boas-vindas" in t
            or "boas vindas" in t
            or "primeros tres depósitos" in t
            or "primer depósito" in t
        ):
            return BonusType.WELCOME_BONUS
        if "no deposit" in t or "sem deposito" in t or "sem depósito" in t or "sin depósito" in t:
            return BonusType.NO_DEPOSIT
        if "cashback" in t or "reembolso" in t:
            return BonusType.CASHBACK
        if (
            "free spin" in t
            or "giros gratis" in t
            or "giros grátis" in t
            or ("giros" in t and ("gratis" in t or "gratuitos" in t))
        ):
            return BonusType.FREE_SPINS
        if "loyalty" in t or "fidelidade" in t or "fidelidad" in t:
            return BonusType.LOYALTY
        if "%" in t and ("deposit" in t or "depósito" in t or "match" in t or "bono" in t):
            return BonusType.DEPOSIT_MATCH
        return BonusType.UNKNOWN

    def extract_amount(self, text: str) -> tuple[float, str]:
        for pattern in AMOUNT_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            groups = match.groups()
            if len(groups) == 2:
                a, b = groups
                if a in CURRENCY_MAP or a.upper() in CURRENCY_MAP:
                    return _to_float(b), CURRENCY_MAP.get(a, CURRENCY_MAP.get(a.upper(), "USD"))
                if b.upper() in CURRENCY_MAP or b in CURRENCY_MAP:
                    return _to_float(a), CURRENCY_MAP.get(b, CURRENCY_MAP.get(b.upper(), "USD"))
        return 0.0, "USD"

    def extract_wagering(self, text: str) -> float:
        if NO_WAGERING_RE.search(text):
            return 0.0
        for pattern in (WAGERING_RE, WAGERING_SHORT_RE):
            match = pattern.search(text)
            if match:
                return _to_float(match.group(1))
        return 30.0

    def extract_expiry(self, text: str) -> tuple[int, Optional[int]]:
        hour = EXPIRY_HOUR_RE.search(text)
        day = EXPIRY_DAY_RE.search(text)
        expiry_hours = int(hour.group(1)) if hour else None
        expiry_days = int(day.group(1)) if day else (1 if expiry_hours else 30)
        if expiry_hours and not day:
            expiry_days = max(1, expiry_hours // 24) if expiry_hours >= 24 else 0
        return expiry_days, expiry_hours

    def extract_game_restrictions(self, text: str) -> list[str]:
        t = text.lower()
        found = [kw for kw in GAME_KEYWORDS if kw in t]
        # Prefer explicit "only" / "excluded" phrases when present
        only = re.findall(r"(?:only|apenas)\s+([a-zA-Z\s,]{3,40})", text, re.I)
        excluded = re.findall(r"(?:excluded|exclu[ií]d[oa]s?)\s*:?\s*([a-zA-Z\s,]{3,60})", text, re.I)
        for chunk in only + excluded:
            for part in re.split(r",|/| and | e ", chunk):
                part = part.strip().lower()
                if part and part not in found:
                    found.append(part)
        return found[:12]

    def analyze(self, text: str) -> ExtractedBonusFields:
        amount, currency = self.extract_amount(text)
        match_pct = None
        m = MATCH_PERCENT_RE.search(text)
        if m:
            match_pct = _to_float(m.group(1))

        free_spins = None
        fs = FREE_SPINS_RE.search(text)
        if fs:
            free_spins = int(fs.group(1))

        min_deposit = 0.0
        md = MIN_DEPOSIT_RE.search(text)
        if md:
            min_deposit = _to_float(md.group(2))

        max_bet = None
        mb = MAX_BET_RE.search(text)
        if mb:
            max_bet = _to_float(mb.group(2))

        expiry_days, expiry_hours = self.extract_expiry(text)

        return ExtractedBonusFields(
            bonus_type=self.identify_type(text),
            amount=amount,
            currency=currency,
            match_percent=match_pct,
            free_spins=free_spins,
            wagering_multiple=self.extract_wagering(text),
            min_deposit=min_deposit,
            max_bet_during_bonus=max_bet,
            expiry_days=expiry_days,
            expiry_hours=expiry_hours,
            game_restrictions=self.extract_game_restrictions(text),
        )


def extract_bonus_fields(text: str) -> ExtractedBonusFields:
    return BonusNLPAnalyzer().analyze(text)
