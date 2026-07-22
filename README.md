# Iron Security — Command Hub

> Painel unificado de todas as ferramentas Iron Security e Lucky Gaming.

## O que é

Central de operações que consolida em uma única interface todos os serviços web, APIs e ferramentas CLI/desktop do ecossistema Iron Security.

## Funcionalidades

- Catálogo completo de ferramentas por vertical (OSINT, Red Team, CSIRT, Threat Intel, iGaming)
- Health check em tempo real de serviços publicados
- Busca e filtros por categoria
- Design system Iron Security (dark, minimalista, SOC-grade)

## Stack

- **Frontend**: React 19 + Vite + TypeScript
- **Backend**: Go (health probes + static serve)

## Instalação e execução

```bash
cd ~/iron-hub
npm ci && npm run build
rm -rf api/dist && cp -r dist api/dist
cd api && go build -o ../iron-hub-server .
cd .. && chmod +x start.sh && ./start.sh
```

Acesse: **http://127.0.0.1:3900**

## Serviços satellite (LLM lab)

| Serviço | Path | Porta |
|---------|------|-------|
| Qwen / Ollama | `services/qwen-uncensored/` | 8780 |
| Open WebUI | `services/open-webui/` | 3080 |

```bash
sudo cp deploy/iron-hub.service deploy/iron-services.target /etc/systemd/system/
sudo cp services/qwen-uncensored/deploy/qwen-uncensored.service /etc/systemd/system/
sudo cp services/open-webui/deploy/open-webui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now qwen-uncensored open-webui iron-hub
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `IRON_HUB_PORT` | `3900` | Porta do servidor |

## Serviços monitorados

Inclui **Iron Open WebUI** em `http://127.0.0.1:3080` (LLM local Qwen3 via Ollama).

| Ferramenta | Porta | Vertical |
|------------|-------|----------|
| Iron OSINT (Mosint) | 8787 | OSINT |
| Iron OSINT Mapping | 8789 | OSINT |
| Iron MAVERICK | 8766 | Red Team |
| Iron Pentest Ops | 8788 | Red Team |
| Iron BurpGPT | 8772 | Red Team |
| O365 CSIRT Dashboard | 8000 | CSIRT |
| DarkWeb Forums Tracker | 13200 | Threat Intel |
| Dark Web Observatory | 8791 | Threat Intel |
| Robin OSINT | 18501 | Threat Intel |
| MoneyPrinterTurbo | 8502 | Conteúdo |
| Bot Live Betting | 3000 | iGaming |
| Onboarding Casas | 3001 | iGaming |

## Desenvolvimento

```bash
npm run dev          # frontend :3900 (proxy /api -> :3901)
# Em outro terminal, após build:
IRON_HUB_PORT=3901 ./iron-hub-server
```
