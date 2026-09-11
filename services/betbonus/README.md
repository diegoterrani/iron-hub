# BetBonus AI

Harness **Red Team** de integridade do produto **Casino Online** (piloto 3 casas Lucky Gaming):

**sessão → wallet → catálogo → slots/crash/mesa → timers → promo → jackpot → saque**

Bônus é **um eixo**, não o produto. Uso autorizado pelo operador (CEO/CISO). Sem manipulação de RNG.

Ver [docs/INTEGRITY.md](docs/INTEGRITY.md).

Harness **Red Team** de abuso de bônus iGaming (piloto 4Play.game):

**Scrape → Parse → NLP → Score → Abuse Score → Conversão → Oracle de saque** + dashboard.

Uso autorizado pelo operador da casa (CEO/CISO) para testar campanhas antes/durante o lançamento.

## Iron Hub

Integrado no Iron Hub como **`betbonus`** (categoria iGaming):

- Gateway: `/t/betbonus/`
- Upstream: `127.0.0.1:8010`
- Health: `/api/health`
- Unit: `betbonus.service`

Após login no Hub, abra o card **BetBonus AI**.

```bash
sudo systemctl status betbonus
sudo systemctl restart betbonus
```

## Quick start (standalone)

```bash
cd /home/ubuntu/iron-tools/iron-hub/services/betbonus
cp -n .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build do dashboard (uma vez / após mudanças no frontend)
# O dist versionado já sobe o console; rebuild só se alterar o React.
cd dashboard && npm install && npm run build && cd ..

# Subir API + dashboard (loopback — acesso via Hub)
python -m src.main api --host 127.0.0.1 --port 8010
```

Abra:

- Via Hub: `/t/betbonus/` — card **Casino Integrity**
- Direto: http://127.0.0.1:8010/
- API docs: http://127.0.0.1:8010/api/docs

> Porta padrão `8010` (evita conflito com outros serviços em `:8000`).

## Dev frontend (hot reload)

```bash
# terminal 1
python -m src.main api --port 8010

# terminal 2
cd dashboard && npm run dev
# → http://127.0.0.1:5173 (ajuste o proxy em vite.config.ts se necessário)
```

## Páginas do dashboard

| Página | Função |
|--------|--------|
| **Console** | Operação: sessões, cobertura, executar DRY/PROBE |
| **Agentes** | Execução seletiva de cenários por casa |
| **Admin** | Tokens das 3 casas + LLM planner |
| **Runs** | Histórico de execuções |
| **Jornada** | Casa → Scout → Auth → Discovery → Ledger → **Abuse/Saque** (legado promo) |
| Carteira | Ledger ops + saldo real 4Play (`/api/wallet`) |
| Abuse API | `/api/abuse/snapshot`, `/score`, `/oracle/withdraw`, `/findings` |
| LLM (Maverick) | `/api/llm/status`, `/api/llm/model`, `/api/llm/ping`, `/api/abuse/llm/analyze` — OpenRouter (DeepSeek V3.1, Dolphin Venice) ou **Qwen3 27B local** (llama.cpp) |
| Logs da jornada | `/logs` + `/api/journey/sessions*` — sessão detalhada Casa→Abuse (`data/journey_sessions.json`) |
| PAGOL adapter | Live API `pagol_bet_br` · balance/bonuses/promocodes/withdraw preflight |

LLM: padrão **Dolphin Mistral 24B Venice** via OpenRouter; a chave continua compartilhada com o Maverick (`OPENROUTER_API_KEY`). DeepSeek segue disponível no catálogo. **Qwen3 27B local** (`qwen38-27b-hauhau`) roda em `127.0.0.1:8082` (llama.cpp) — sem API key, selecionável via Admin ou `BETBONUS_LLM=qwen38-27b-hauhau`.
| Bonuses | Inventário com filtros + score breakdown |
| Pipeline | Fixture, upload HTML, colar HTML, URL live |
| Auth | Token/login 4Play |
| Activity | Feed operacional (auto-refresh) |

Ver fluxo em [docs/JOURNEY.md](docs/JOURNEY.md).

## CLI

```bash
python -m src.main demo
python -m src.main score
python -m src.integrity catalog
python -m src.integrity sims
pytest -q
```

## Estrutura

```
src/integrity/          # Produto cassino: adapters, catálogo, workers, sims, planner
src/api.py              # FastAPI admin + serve dashboard/dist
src/pipeline/           # Orquestração promo
src/scrapers/ nlp/ scoring/ storage/ notify/
configs/integrity/      # scenarios.yaml (eixos do cassino)
dashboard/              # React + Vite
tests/fixtures/         # HTML de exemplo
```
