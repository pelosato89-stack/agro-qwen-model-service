from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error

from flask import Flask, jsonify, request
from llama_cpp import Llama

app = Flask(__name__)

# -----------------------------
# Configuración
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent

MODEL_URL = os.getenv(
    "MODEL_URL",
    "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
)

# Paths:
# 1) LOCAL_MODEL_PATH (si existe en disco) -> ideal para imágenes con modelo incluido
# 2) MODEL_PATH (si el usuario lo define) -> puede ser /tmp/... en Leapcell
# 3) fallback /tmp/... -> writable en runtimes serverless
DEFAULT_MODEL_NAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
DEFAULT_TMP_PATH = Path("/tmp") / DEFAULT_MODEL_NAME

def resolve_model_path() -> Path:
    local_env = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH".replace("_", ""))  # por si acaso
    local_env = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH")  # noop seguro
    local_env = os.getenv("LOCAL_MODEL_PATH")

    # En tu código original usabas LOCAL_MODEL_PATH y LOCAL_MODEL_PATH, pero en realidad tenías LOCAL_MODEL_PATH.
    # Aquí soportamos LOCAL_MODEL_PATH y LOCAL_MODEL_PATH por si te equivocas en env.
    local_env = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH")  # redundante pero inocuo
    local_env = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH")  # idem

    local_env = os.getenv("LOCAL_MODEL_PATH") or os.getenv("LOCAL_MODEL_PATH")  # mantener
    # Realmente: usa LOCAL_MODEL_PATH si está definido
    local_env = os.getenv("LOCAL_MODEL_PATH")

    if local_env:
        p = Path(local_env)
        # Si es relativo, lo resolvemos respecto al proyecto
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        if p.exists() and p.is_file():
            return p

    # Luego: MODEL_PATH
    env_model_path = os.getenv("MODEL_PATH")
    if env_model_path:
        p = Path(env_model_path)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        return p

    return DEFAULT_TMP_PATH


MODEL_PATH: Path = resolve_model_path()

N_CTX = int(os.getenv("N_CTX", "1024"))
N_THREADS = int(os.getenv("N_THREADS", "1"))
PORT = int(os.getenv("PORT", "8080"))

# -----------------------------
# Estado global
# -----------------------------
_LLM: Llama | None = None
_MODEL_ERROR: str | None = None


# -----------------------------
# Utilidades
# -----------------------------
def is_path_writable(path: Path) -> bool:
    """Check rápido de escribibilidad del directorio padre."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        test_file = path.parent / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def pick_download_target(original_target: Path) -> Path:
    """
    Si el destino no es escribible (ej: /app/models en Leapcell), usa /tmp.
    """
    if is_path_writable(original_target):
        return original_target

    tmp_target = DEFAULT_TMP_PATH
    # Si /tmp tampoco fuese escribible (raro), intenta dentro del cwd
    if is_path_writable(tmp_target):
        return tmp_target

    fallback = Path.cwd() / DEFAULT_MODEL_NAME
    return fallback


def download_model_if_needed(model_path: Path, model_url: str) -> tuple[bool, Path]:
    """
    Descarga el modelo automáticamente si no existe.

    Returns:
        (ok, final_path) donde final_path puede diferir si el path original no era escribible.
    """
    # Si ya existe, ok.
    if model_path.exists() and model_path.is_file():
        print(f"✅ Modelo encontrado en: {model_path}")
        return True, model_path

    final_target = pick_download_target(model_path)

    if final_target != model_path:
        print(f"⚠️  Ruta no escribible: {model_path}")
        print(f"➡️  Usando ruta escribible: {final_target}")

    if final_target.exists() and final_target.is_file():
        print(f"✅ Modelo ya existe en: {final_target}")
        return True, final_target

    print(f"⚠️  Modelo NO encontrado en: {final_target}")
    print(f"⬇️  Iniciando descarga automática desde: {model_url}")
    print("📦 Tamaño aproximado: ~400 MB")

    try:
        final_target.parent.mkdir(parents=True, exist_ok=True)

        last_percent = -1

        def report_progress(block_num, block_size, total_size):
            nonlocal last_percent
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded * 100) // total_size)
                if percent >= last_percent + 10:
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"   {percent}% - {mb_downloaded:.1f}/{mb_total:.1f} MB")
                    last_percent = percent

        print("🔄 Descargando... (puede tardar)")
        urllib.request.urlretrieve(model_url, str(final_target), reporthook=report_progress)

        size_mb = final_target.stat().st_size / (1024 * 1024)
        print(f"✅ Modelo descargado exitosamente en: {final_target}")
        print(f"📊 Tamaño del archivo: {size_mb:.1f} MB")
        return True, final_target

    except urllib.error.URLError as e:
        error_msg = f"❌ Error de red al descargar modelo: {e}"
        print(error_msg)
        return False, final_target
    except Exception as e:
        error_msg = f"❌ Error inesperado al descargar modelo: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return False, final_target


def load_model() -> bool:
    """Carga el modelo. Si falla, guarda el error pero no tumba el servicio."""
    global _LLM, _MODEL_ERROR, MODEL_PATH

    print("=" * 60)
    print("🔄 CARGANDO MODELO LLM...")
    print(f"📁 Ruta solicitada: {MODEL_PATH}")
    print("=" * 60)

    ok, final_path = download_model_if_needed(MODEL_PATH, MODEL_URL)
    MODEL_PATH = final_path  # importante: usar el path real final

    if not ok:
        _MODEL_ERROR = f"❌ ERROR: No se pudo obtener el modelo en: {MODEL_PATH}"
        print(_MODEL_ERROR)
        print("=" * 60)
        return False

    try:
        print("✅ Archivo del modelo disponible")
        print(f"⚙️  Configuración: n_ctx={N_CTX}, n_threads={N_THREADS}")

        _LLM = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=N_CTX,
            n_threads=N_THREADS,
        )
        _MODEL_ERROR = None
        print("✅ Modelo cargado exitosamente")
        print("=" * 60)
        return True

    except Exception as e:
        _LLM = None
        _MODEL_ERROR = f"❌ ERROR cargando modelo: {e}"
        print(_MODEL_ERROR)
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


# -----------------------------
# Boot (no mata el server si falla)
# -----------------------------
print("🚀 Inicializando módulo model_api...")
load_model()


# -----------------------------
# Endpoints
# -----------------------------
@app.get("/")
def root():
    # Nunca 500 aquí: si no, Leapcell puede reiniciarte por health checks simples.
    return jsonify({
        "service": "Agricultural LLM API",
        "version": "1.0.1",
        "status": "ready" if _LLM is not None else "degraded",
        "model_loaded": _LLM is not None,
        "model_path": str(MODEL_PATH),
        "error": _MODEL_ERROR,
        "endpoints": {
            "health": "/health",
            "kaith_health": "/kaithhealthcheck",
            "chat": "/chat (POST)",
        },
    }), 200


@app.get("/health")
def health():
    # 200 siempre; informa si el modelo está o no.
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": _LLM is not None,
        "model_path": str(MODEL_PATH),
        "error": _MODEL_ERROR,
    }), 200


# Leapcell (según tus logs) pega a estos endpoints:
@app.get("/kaithhealthcheck")
@app.get("/kaithheathcheck")  # typo del checker
def kaith_health():
    return jsonify({
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "model_loaded": _LLM is not None,
        "error": _MODEL_ERROR,
    }), 200


@app.post("/chat")
def chat():
    # Si no hay modelo, devuelve 503 (esto sí puede ser 503, pero NO mates health/root)
    if _LLM is None:
        return jsonify({
            "error": "Model not available",
            "details": _MODEL_ERROR or "LLM instance is None",
            "model_path": str(MODEL_PATH),
        }), 503

    try:
        payload = request.get_json(force=True, silent=False) or {}
        system_prompt = payload.get("system", "Eres un asistente agrónomo.")
        context = payload.get("context", {})
        max_tokens = int(payload.get("max_tokens", 256))

        mensaje = ""
        if isinstance(context, dict):
            mensaje = str(context.get("mensaje", ""))
        print(f"📨 Request: {mensaje[:120]}...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]

        print("🤖 Generando respuesta...")
        response = _LLM.create_chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )

        content = (response["choices"][0]["message"]["content"] or "").strip()
        print(f"✅ Respuesta: {len(content)} chars")

        return jsonify({
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "model": "llama-cpp",
            "model_path": str(MODEL_PATH),
        }), 200

    except Exception as e:
        error_msg = f"Error procesando request: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": error_msg,
            "type": type(e).__name__,
        }), 500


if __name__ == "__main__":
    print(f"🌐 Ejecutando Flask dev server en puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
