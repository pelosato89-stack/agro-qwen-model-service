from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request
from llama_cpp import Llama

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = os.getenv(
    "LOCAL_MODEL_PATH", str(BASE_DIR / "models/qwen2.5-3b-instruct-q4_k_m.gguf")
)
N_CTX = int(os.getenv("N_CTX", "2048"))
N_THREADS = int(os.getenv("N_THREADS", "1"))

app = Flask(__name__)
_LLM: Llama | None = None


def get_llm() -> Llama:
    global _LLM
    if _LLM is None:
        if not Path(MODEL_PATH).exists():
            raise RuntimeError(f"No se encontró el modelo local en {MODEL_PATH}.")
        _LLM = Llama(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_threads=N_THREADS,
        )
    return _LLM


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat() -> dict[str, str]:
    payload = request.get_json(force=True)
    system_prompt = payload.get("system", "")
    context = payload.get("context", {})
    max_tokens = int(payload.get("max_tokens", 300))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]
    llm = get_llm()
    response = llm.create_chat_completion(
        messages=messages,
        temperature=0.2,
        max_tokens=max_tokens,
    )
    content = response["choices"][0]["message"]["content"] or ""
    return {"content": content}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
