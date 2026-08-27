# Iron local LLM — llama.cpp OpenAI-compatible (host)
# Alias live: qwen3.5-27b-uncensored-aggressive
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1
export API_KEY_FILE="${API_KEY_FILE:-$HOME/.config/llama/api_key}"
if [ -r "$API_KEY_FILE" ]; then
  export OPENAI_API_KEY="$(tr -d '\n\r' < "$API_KEY_FILE")"
else
  export OPENAI_API_KEY="${OPENAI_API_KEY:-local}"
fi
export OPENAI_MODEL=qwen3.5-27b-uncensored-aggressive
# LiteLLM / Strix form:
#   openai/qwen3.5-27b-uncensored-aggressive
