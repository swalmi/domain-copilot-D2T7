#!/bin/sh
set -e

# Start the Ollama server in the background
ollama serve &
SERVER_PID=$!

# Give the server a moment to start
sleep 3

# Pull required models (idempotent: no-op if already downloaded)
for model in $(echo "$OLLAMA_MODELS" | tr ',' ' '); do
    echo "[ollama-init] Pulling model: $model"
    ollama pull "$model" || echo "[ollama-init] WARNING: failed to pull $model"
done

# Warm both models into memory (OLLAMA_KEEP_ALIVE=-1 keeps them resident) so
# per-request cold loads never spike RAM on this small host.
for model in $(echo "$OLLAMA_MODELS" | tr ',' ' '); do
    echo "[ollama-init] Warming model: $model"
    printf 'hello' | ollama run "$model" --verbose 2>/dev/null >/dev/null || \
    curl -s http://127.0.0.1:11434/api/embeddings -d "{\"model\":\"$model\",\"prompt\":\"warmup\"}" >/dev/null || \
    echo "[ollama-init] WARNING: warmup failed for $model"
done

echo "[ollama-init] Models ready. Ollama serving on :11434"

# Keep server in foreground
wait $SERVER_PID