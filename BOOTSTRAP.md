# Iron Hub — Bootstrap Context

## Stack
- **Frontend:** React 19 + Vite + TypeScript (`src/`)
- **Backend:** Go (`api/main.go`) — health probes + static file server
- **Port:** `3900` (`IRON_HUB_PORT`)

## Arquitetura
```
Browser → iron-hub-server :3900
           ├─ /           SPA (Vite build embutido em api/dist)
           ├─ /api/services
           └─ /api/health  → probes paralelos nos serviços registrados
```

## Comandos
```bash
npm ci && npm run build
rm -rf api/dist && cp -r dist api/dist
cd api && go build -o ../iron-hub-server .
./start.sh
# ou: sudo systemctl restart iron-hub.service
```

## Serviços satellite (deploy)
- `services/open-webui/` — UI LLM em `:3080` (Ollama/qwen)
- `services/qwen-uncensored/` — Ollama local em `:8780`

## Registry
Fonte de verdade dos cards: `src/data/services.ts` + lista espelhada em `api/main.go`.

## Pontos de atenção
- Health checks são best-effort; falha de um serviço não derruba o hub
- Sem autenticação — lab interno / firewall de borda
