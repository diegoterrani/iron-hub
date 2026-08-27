# Iron Open WebUI

Chat via **OpenRouter** (OpenAI-compatible), integrado ao Iron Hub.

| Item | Valor |
|------|--------|
| Bind interno | `127.0.0.1:3080` (não público) |
| Hub (:443) | sem cookie `iron_app` → `/` redireciona a `/console/` |
| WebUI (:443) | cookie `iron_app=open-webui` → `/` é a home da Open WebUI |
| Backend LLM | `https://openrouter.ai/api/v1` |
| Default model | `deepseek/deepseek-chat-v3.1` (com Iron Lab Host tools) |
| Opções de uso (pinned) | `dolphin-venice` → `cognitivecomputations/dolphin-mistral-24b-venice-edition` (**chat-only**, sem tools) |
| Extra workspace | `dolphin-venice` — Venice/OpenRouter não expõe tool use; Iron Lab Host, builtins (`get_current_timestamp`) e skills ficam desligados neste modelo |

### Boot
`open-webui.service` sobe com Docker (sem dependência do LLM local/Qwen).
Em todo start/reload, `open-webui-sync-model` realinha o DB (base URL + chave OpenRouter).

### Rotas
- **Sem cookie** → `/` vai para o Hub (`/console/`)
- **Card Open WebUI** → `/go/open-webui` → cookie + `/`
- **`/console/`** → Hub
- **`/go/hub`** → limpa o cookie da WebUI e volta ao Hub

### Operação
```bash
sudo systemctl start open-webui
sudo systemctl status open-webui
curl -sS http://127.0.0.1:3080/health
/home/ubuntu/bin/open-webui-sync-model
```

Credenciais: `services/open-webui/.env` (`OPENAI_API_KEY` = chave OpenRouter).

### Iron Lab Host (tools)
Tool Workspace → `iron-lab-agent` (`127.0.0.1:8793`).
Ver `../iron-lab-agent/README.md`.
