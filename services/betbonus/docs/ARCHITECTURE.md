# BetBonus AI — Architecture

## Pipeline

```
Scrape → Parse → NLP → Attractiveness Score → Abuse Score → Conversion Snapshot → Withdraw Oracle → Findings
```

## Modules

| Module | Role |
|--------|------|
| `src/scrapers` | HTML/API adapters (4Play: promos, wallet, withdraw) |
| `src/nlp` | Extract wagering, amount, expiry, restrictions |
| `src/scoring` | Attractiveness 0–100 + **AbuseScoringEngine** |
| `src/abuse` | Conversion classifier + WithdrawalOracle + findings store |
| `src/storage` | JSON store (bonuses, wallet ops, abuse_findings) |
| `src/notify` | Activity feed |
| `src/pipeline` | Orchestrates scrape/score flow |
| `src/api` | FastAPI admin + abuse endpoints |

## Scoring factors

1. Real bonus value adjusted by wagering
2. Wagering multiple bands
3. Expiry speed penalty
4. Min deposit friction
5. Game restrictions
6. Type prior (no-deposit / free spins / cashback)
7. Max-bet-during-bonus penalty

## Next steps

1. Validate on 3–5 smaller platforms with saved HTML dumps
2. Add Postgres + Redis
3. Train spaCy NER on labeled T&Cs
4. React dashboard + websocket notifications
5. Expand live scrapers only with compliant/authorized access
