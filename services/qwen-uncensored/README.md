# Qwen3 Abliterated (uncensored) — local API (GPU)

OpenAI-compatible endpoint for Iron tools / MAVERICK on **g4dn.xlarge** (16 GB RAM + Tesla T4 16 GB).

## Endpoint

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:8780/v1` |
| Model (alias) | `qwen3-local:14b` |
| Upstream | `huihui_ai/qwen3-abliterated:14b` |
| Family | Qwen3 abliterated · ~9 GB Q4 · `/no_think` |
| API key | any non-empty string (e.g. `local-secret`) |

LiteLLM / Strix / MAVERICK model id:

```text
openai/qwen3-local:14b
```

## Why 14B (not 30B) on this host

- T4 has **16 GB VRAM** — 14B (~9 GB) fits with KV cache; 30B (~18 GB) does **not**
- Host has only **16 GB RAM** — installing NVIDIA stack without swap previously froze the instance (OOM)
- GPU inference ~20–25 tok/s after warm vs crawling on CPU

Do **not** `ollama run qwen3-local:30b` on this instance.

## Safe install procedure (avoid freezes)

1. Add **8 GB+ swap** before any NVIDIA/apt heavy work
2. Stop heavy containers (`qwen-uncensored`, `open-webui`)
3. Install **driver once** (already done: 550.x); then only `nvidia-container-toolkit`
4. `nvidia-ctk runtime configure --runtime=docker` + restart Docker
5. Bring Ollama up with `gpus: all` and `mem_limit: 10g`
6. Pull **14B only**, create alias, warm model

## Examples

```bash
curl http://127.0.0.1:8780/v1/chat/completions \
  -H 'Authorization: Bearer local-secret' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3-local:14b",
    "messages": [{"role":"user","content":"/no_think\nhi"}],
    "max_tokens": 128
  }'
```

```bash
source /home/kali/qwen-uncensored/env.sh
```

## Ops

```bash
cd /home/kali/qwen-uncensored
docker compose up -d
docker exec qwen-uncensored ollama pull huihui_ai/qwen3-abliterated:14b
docker exec -i qwen-uncensored sh -c 'cat >/tmp/Modelfile <<EOF
FROM huihui_ai/qwen3-abliterated:14b
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
SYSTEM """/no_think
You are a concise cybersecurity assistant for authorized red-team and pentest work. Answer directly.
"""
EOF
ollama create qwen3-local:14b -f /tmp/Modelfile'
# preload into VRAM
curl -s http://127.0.0.1:8780/api/generate -d '{"model":"qwen3-local:14b","keep_alive":"24h","think":false}'
docker compose logs -f
nvidia-smi
```
