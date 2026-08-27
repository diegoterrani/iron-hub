# Iron Hub — Bootstrap Context

## Stack
- **Frontend:** React 19 + Vite + TypeScript (`src/`)
- **Backend:** Go (`api/main.go`) — auth session, health probes, reverse-proxy gateway, static SPA
- **Port:** `3900` (`IRON_HUB_PORT`)

## Auth → Hub → Ferramenta
```
Browser
  └─ login (cookie HttpOnly iron_session)
       └─ Iron Hub :3900
            ├─ /                     SPA (login ou catálogo)
            ├─ /hub/api/*            control plane (auth)
            └─ /t/{tool-id}/*  ──►   127.0.0.1:{porta interna}
```

Ferramentas escutam só em **loopback**. O browser nunca recebe host:porta interno.

## Credenciais locais
Arquivo `.env` (não commitado):

| Variável | Descrição |
|----------|-----------|
| `IRON_HUB_USER` | usuário local (default `iron`) |
| `IRON_HUB_PASS` | senha |
| `IRON_HUB_SESSION_SECRET` | HMAC da sessão |

Senha atual também em `../.hub-password` neste host.

## Comandos
```bash
npm ci && npm run build
rm -rf api/dist && cp -r dist api/dist
cd api && go build -o ../iron-hub-server .
set -a && source .env && set +a
./iron-hub-server
# ou: sudo systemctl restart iron-hub.service
```

## Endpoints
| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/hub/api/login` | não | `{username,password}` → cookie |
| POST | `/hub/api/logout` | sim | limpa sessão |
| GET | `/hub/api/me` | sim | usuário atual |
| GET | `/hub/api/health` | sim | probes internos |
| GET | `/hub/api/services` | sim | catálogo sem URLs internas |
| * | `/t/{id}/…` | sim | proxy strip-prefix → ferramenta |

## Pontos de atenção
- Health checks são best-effort; falha de um serviço não derruba o hub
- Proxy reescreve redirects e paths absolutos comuns (`/api`, `/assets`, …)
- Frontends Iron usam `gatewayPrefix()` para prefixar fetches sob `/t/{id}`
- iGaming no repo: `services/betbonus/` (:8010) e `services/casino-bot/` (:8011)
