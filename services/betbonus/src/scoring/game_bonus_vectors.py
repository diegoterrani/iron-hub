from __future__ import annotations

import re
from typing import Any

from src.models.abuse import AbuseSeverity
from src.models.bonus import BonusOffer, BonusType


# Sinais textuais: bônus jogável sem rollover / sem depósito / contribuição 0%
NO_ROLLOVER_RE = re.compile(
    r"(?:sem\s+rollover|sem\s+requisito(?:\s+de\s+aposta)?|no\s+wager(?:ing)?|"
    r"zero\s+wager(?:ing)?|wager(?:ing)?\s*(?:free|zero)|0\s*[xX×]\s*(?:wager|rollover|aposta)?|"
    r"rollover\s*(?:zero|0)|playthrough\s*(?:free|zero|0)|"
    r"sem\s+rollover\s+para\s+(?:jogar|apostar)|bonus\s+sem\s+rollover)",
    re.IGNORECASE,
)
NO_DEPOSIT_RE = re.compile(
    r"(?:sem\s+dep[oó]sito|no\s+deposit|sin\s+dep[oó]sito|free\s+bonus|"
    r"b[oô]nus\s+gr[aá]tis(?:\s+sem\s+dep[oó]sito)?|dep[oó]sito\s+n[aã]o\s+obrigat)",
    re.IGNORECASE,
)
ZERO_CONTRIB_RE = re.compile(
    r"(?:contribui[cç][aã]o|contribution|aporte)\s*(?:de\s*)?(?:0|zero)\s*%|"
    r"(?:0|zero)\s*%\s*(?:de\s*)?(?:contribui|contribution|aporte)|"
    r"(?:jogos?|games?)\s+(?:com\s+)?(?:contribui[cç][aã]o|contribution)\s*(?:0|zero)|"
    r"excluded\s+from\s+wagering|n[aã]o\s+contam?\s+para\s+(?:o\s+)?rollover|"
    r"n[aã]o\s+contribuem?\s+para\s+(?:o\s+)?(?:rollover|wagering)",
    re.IGNORECASE,
)
BONUS_PLAYABLE_RE = re.compile(
    r"(?:jog(?:ar|ue)|play|apostar)\s+(?:com\s+)?(?:o\s+)?(?:b[oô]nus|bonus)|"
    r"(?:b[oô]nus|bonus)\s+(?:pode\s+ser\s+)?(?:usado|utilizad[oa]|v[aá]lido)\s+(?:em|nos?|para)|"
    r"(?:v[aá]lido|available|eligible)\s+(?:em|for|on)\s+(?:slots?|cassino|casino|jogos?|games?)",
    re.IGNORECASE,
)
HIGH_EV_GAME_RE = re.compile(
    r"\b(?:crash|mines|plinko|dice|limbo|roulette|ruleta|blackjack|"
    r"baccarat|live\s+casino|cassino\s+ao\s+vivo|aviator|spaceman|"
    r"table\s+games?|jogos?\s+de\s+mesa)\b",
    re.IGNORECASE,
)


def detect_game_bonus_vectors(offer: BonusOffer) -> list[dict[str, Any]]:
    """
    Hipóteses de abuso: jogos que permitem rodar bônus sem rollover
    e/ou sem depósito (gap de contribuição / elegibilidade).
    """
    text = " ".join(
        x
        for x in (
            offer.title,
            offer.raw_text,
            " ".join(offer.game_restrictions),
            offer.bonus_type.value,
        )
        if x
    )
    text_l = text.lower()
    vectors: list[dict[str, Any]] = []

    no_rollover_text = bool(NO_ROLLOVER_RE.search(text))
    no_deposit_text = bool(NO_DEPOSIT_RE.search(text)) or offer.bonus_type == BonusType.NO_DEPOSIT
    zero_contrib = bool(ZERO_CONTRIB_RE.search(text))
    bonus_playable = bool(BONUS_PLAYABLE_RE.search(text)) or bool(offer.game_restrictions) or True
    high_ev = sorted({m.group(0).lower() for m in HIGH_EV_GAME_RE.finditer(text)})
    wager_zero = offer.wagering_multiple <= 0
    wager_very_low = 0 < offer.wagering_multiple <= 5
    unrestricted = len(offer.game_restrictions) == 0

    # 1) Bônus jogável sem rollover (texto ou múltiplo 0)
    if (no_rollover_text or wager_zero) and bonus_playable:
        vectors.append(
            _vec(
                "bonus_play_no_rollover",
                "Jogos permitem usar bônus sem rollover",
                AbuseSeverity.CRITICAL if (unrestricted or high_ev) else AbuseSeverity.HIGH,
                "T&Cs/heurística indicam bônus utilizável em jogos com rollover 0 "
                f"(wagering={offer.wagering_multiple}x"
                + (", sinal textual sem rollover" if no_rollover_text else "")
                + ").",
                "Claim do bônus → abrir jogo elegível com bonusBalance → confirmar se "
                "ganhos caem em balance sacável sem dayTotals/rollover.",
                {
                    "wagering_multiple": offer.wagering_multiple,
                    "no_rollover_text": no_rollover_text,
                    "unrestricted_games": unrestricted,
                    "high_ev_games": high_ev,
                },
            )
        )

    # 2) Sem depósito + jogos (multi-account / farm)
    if no_deposit_text and bonus_playable:
        sev = AbuseSeverity.CRITICAL if (wager_zero or no_rollover_text or wager_very_low) else AbuseSeverity.HIGH
        vectors.append(
            _vec(
                "bonus_play_no_deposit",
                "Bônus sem depósito jogável em jogos",
                sev,
                "Oferta sem depósito permite jogar (e potencialmente converter) sem "
                f"fricção de depósito. wagering={offer.wagering_multiple}x, "
                f"min_deposit={offer.min_deposit}.",
                "Conta lab nova → claim no-deposit → jogar título listado → medir se "
                "ganho vira saldo real e se KYC/saque bloqueia.",
                {
                    "min_deposit": offer.min_deposit,
                    "bonus_type": offer.bonus_type.value,
                    "wagering_multiple": offer.wagering_multiple,
                    "high_ev_games": high_ev,
                },
            )
        )

    # 3) Contribuição 0% / jogos que não contam mas ainda consomem/pagam bônus
    if zero_contrib:
        vectors.append(
            _vec(
                "zero_contribution_games",
                "Jogos com contribuição 0% (ou excluídos do rollover)",
                AbuseSeverity.HIGH,
                "Texto menciona contribuição 0% / exclusão de rollover — verificar se "
                "esses jogos ainda aceitam aposta com saldo de bônus (consumo sem progresso) "
                "ou se há bypass de contribuição em títulos high-EV.",
                "Listar jogos citados → apostar com bônus → comparar contribuição "
                "esperada vs rollover restante / bonusBalance.",
                {"high_ev_games": high_ev, "matched": True},
            )
        )

    # 4) Rollover baixo + sem restrição de jogo + high-EV
    if wager_very_low and unrestricted and not no_rollover_text:
        vectors.append(
            _vec(
                "low_wager_unrestricted_games",
                "Rollover baixo sem restrição de jogos",
                AbuseSeverity.HIGH if high_ev else AbuseSeverity.MEDIUM,
                f"Wagering {offer.wagering_multiple}x sem game_restrictions — "
                "atacante pode escolher jogos de baixa house-edge / alta variância "
                "para clear rápido.",
                "Mapear contribuição real por categoria (slots/crash/live) na casa e "
                "validar max-bet durante bônus.",
                {
                    "wagering_multiple": offer.wagering_multiple,
                    "game_restrictions": offer.game_restrictions,
                    "high_ev_games": high_ev,
                },
            )
        )

    # 5) High-EV citados sem exclusão explícita + fricção baixa
    if high_ev and unrestricted and (no_deposit_text or wager_zero or wager_very_low or no_rollover_text):
        vectors.append(
            _vec(
                "high_ev_bonus_eligible",
                f"Jogos high-EV elegíveis ao bônus: {', '.join(high_ev[:5])}",
                AbuseSeverity.HIGH,
                "Títulos de alta EV/variância aparecem no texto e não há exclusão "
                "clara — risco de clear/extração acelerada com bônus.",
                "Confirmar elegibilidade real na UI/API de start do jogo com "
                "bonusBalance > 0 e rollover=0 ou bônus no-deposit.",
                {"games": high_ev},
            )
        )

    # Dedup by id (keep highest severity)
    return _dedup(vectors)


def score_game_bonus_gap(offer: BonusOffer) -> tuple[float, list[dict[str, Any]]]:
    """Pontuação 0–22 somada ao abuse score + lista de vetores."""
    vectors = detect_game_bonus_vectors(offer)
    if not vectors:
        return 0.0, []
    weight = {
        AbuseSeverity.CRITICAL.value: 12.0,
        AbuseSeverity.HIGH.value: 8.0,
        AbuseSeverity.MEDIUM.value: 5.0,
        AbuseSeverity.LOW.value: 3.0,
        AbuseSeverity.INFO.value: 1.0,
    }
    # soma com teto; critical+no_deposit empilha
    total = 0.0
    seen = set()
    for v in vectors:
        if v["id"] in seen:
            continue
        seen.add(v["id"])
        total += weight.get(str(v.get("severity")), 3.0)
    return round(min(22.0, total), 2), vectors


def summarize_platform_game_risk(
    offers: list[BonusOffer],
    *,
    wallet_bonus: float = 0.0,
    wallet_rollover: float = 0.0,
) -> dict[str, Any]:
    """Agrega vetores das offers + sinal de carteira (bonus sem rollover)."""
    all_vectors: list[dict[str, Any]] = []
    for offer in offers:
        vecs = detect_game_bonus_vectors(offer)
        for v in vecs:
            all_vectors.append({**v, "offer_id": offer.id, "offer_title": offer.title})

    wallet_vectors: list[dict[str, Any]] = []
    if wallet_bonus > 0 and wallet_rollover <= 0:
        wallet_vectors.append(
            _vec(
                "wallet_bonus_no_rollover",
                "Carteira: bonusBalance > 0 com rollover 0",
                AbuseSeverity.CRITICAL,
                f"Conta tem bonus={wallet_bonus} e rollover={wallet_rollover}. "
                "Validar se jogos aceitam esse bônus e se ganhos viram saldo sacável.",
                "Abrir jogo elegível com bonusBalance → apostar stake mínimo → "
                "diff balance/bonus/rollover + tentativa de saque controlada.",
                {"bonus": wallet_bonus, "rollover": wallet_rollover},
            )
        )
        all_vectors.append({**wallet_vectors[0], "offer_id": "", "offer_title": "(wallet)"})

    sev_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    all_vectors.sort(
        key=lambda v: sev_rank.get(str(v.get("severity")), 0),
        reverse=True,
    )
    top = all_vectors[:12]
    return {
        "count": len(all_vectors),
        "critical": sum(1 for v in all_vectors if v.get("severity") == "critical"),
        "high": sum(1 for v in all_vectors if v.get("severity") == "high"),
        "items": top,
        "wallet_signal": wallet_vectors[0] if wallet_vectors else None,
        "focus": (
            "Jogos jogáveis com bônus sem rollover / sem depósito"
            if all_vectors
            else "Nenhum sinal textual/heurístico forte de bonus-play gap"
        ),
    }


def _vec(
    vid: str,
    title: str,
    severity: AbuseSeverity,
    rationale: str,
    test_idea: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": vid,
        "title": title,
        "severity": severity.value,
        "rationale": rationale,
        "test_idea": test_idea,
        "evidence": evidence,
        "source": "heuristic",
    }


def _dedup(vectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    best: dict[str, dict[str, Any]] = {}
    for v in vectors:
        prev = best.get(v["id"])
        if prev is None or rank.get(v["severity"], 0) > rank.get(prev["severity"], 0):
            best[v["id"]] = v
    return list(best.values())
