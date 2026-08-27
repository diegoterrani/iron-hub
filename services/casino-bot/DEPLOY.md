# Casino Bot — Deploy (Iron Tools)

Path no Hub: `services/casino-bot/`  
Upstream: [BotYanis/Casino_bot](https://github.com/BotYanis/Casino_bot.git)  
Console: `http://127.0.0.1:8011/`  
Health: `http://127.0.0.1:8011/api/health`  
Unit: `casino-bot.service`  
Hub: `/t/casino-bot/`

Telegram casino (aiogram 2 + SQLite). Interface em **PT-BR**. Deploy em **modo lab**: pagamentos QIWI / YooMoney / Coinbase / CrystalPay **desligados**. O repositório original trazia token Telegram e chave P2P QIWI em texto — essas credenciais **não** entram no runtime.

## Status

| Item | Valor |
|------|-------|
| Container | `iron-casino-bot` |
| Bind | `127.0.0.1:8011` |
| DB | `data/bebra.db` (vazia, não a `bebra.db` do upstream) |
| Telegram | precisa de `TELEGRAM_BOT_TOKEN` no `.env` |

## Subir

```bash
cd /home/ubuntu/iron-tools/iron-hub/services/casino-bot
cp -n .env.example .env
# cole o token do BotFather
nano .env
sudo cp deploy/casino-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now casino-bot
```

Sem token o console fica no ar (`telegram=awaiting_token`). Com token válido o bot entra em polling.

```bash
sudo systemctl status casino-bot
docker compose -f /home/ubuntu/iron-tools/iron-hub/services/casino-bot/docker-compose.yml logs -f
curl -s http://127.0.0.1:8011/api/health
```

## Admin no Telegram

`ADMIN_IDS` = IDs numéricos do Telegram, separados por vírgula. Painel do bot original: comando/fluxo `admin` no perfil.

## Fora de escopo

Não religar processadores de pagamento do autor original. Não apontar este bot para casas de terceiros.
