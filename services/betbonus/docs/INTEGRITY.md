# Casino Integrity — produto Casino Online

Harness de **integridade do cassino** (não só bônus) nas 3 casas Lucky Gaming.

| Casa | Stack | Adapter |
|------|--------|---------|
| pagol.bet.br | Salsa / Lucky | `PagolHouse` |
| 4play.bet.br | SoftBet | `FourPlayBrHouse` |
| 4play.game | 4play API | `FourPlayHouse` — catálogo `GET /casino/games` |

## O que é o produto

Eixos obrigatórios no catálogo (`configs/integrity/scenarios.yaml`):

sessão · wallet · catálogo · slots · crash · mesa · timer · promo · jackpot · saque

Promo/bônus é **um** eixo. Sportsbook e poker P2P estão fora.

## Limites

- Lab autorizado do operador, contas de teste.
- Default `PROBE` **autenticado** (`require_auth=true`). Sem sessão viva a casa fica `BLOCKED` / `auth_required`.
- Token salvo ≠ sessão válida (JWT SoftBet expira). O console pinga `/api/ops/status`.
- `DRY` não exige token (só sims offline).
- Live: `pytest -m live` (PAGOL / 4play) — skip sem token ou com sessão expirada.
- Stake só existiria com `CONFIRM_STAKE` + `confirm_real_bet` — os workers atuais **não** apostam no provider.
- Sem manipulação de RNG, sem predição de crash/slots, sem reverse-engineer de Pragmatic/Spribe WS.
- Play no provider = `SEMI_AUTO` até round-log oficial de operador.

## Como rodar

```bash
cd /home/ubuntu/iron-tools/BetBonusAI
source .venv/bin/activate

python -m src.integrity catalog
python -m src.integrity sims

# API (via Hub /t/betbonus/ ou :8010)
curl -s http://127.0.0.1:8010/api/integrity/catalog | jq .coverage.mode_counts
curl -s -X POST http://127.0.0.1:8010/api/integrity/run \
  -H 'Content-Type: application/json' \
  -d '{"run_mode":"PROBE","require_auth":true,"plan":true,"persist":true}'
```

UI: rota **Integrity** (home). Jornada de bônus permanece em `/journey`.

## Flags

| Flag | Default | Efeito |
|------|---------|--------|
| `run_mode=DRY` | — | Não chama APIs da casa (sims offline ainda rodam) |
| `run_mode=PROBE` | sim | Launch/wallet/catálogo; sem spin no provider |
| `confirm_real_bet` | false | Ignorado enquanto não houver worker de stake |
| `kill_switch.<casa>` | false | YAML: pula a casa inteira |

Cap: `max_lab_stake_brl: 5.0` no YAML.

## Cobertura

Medida por eixo (`AUTOMATED` / `SEMI_AUTO` / `UNSUPPORTED` / `BLOCKED`), **não** por bônus convertido.

Artefato: `data/integrity_runs.json`.
