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

# Configuración
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = os.getenv(
    "LOCAL_MODEL_PATH", str(BASE_DIR / "models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
)
N_CTX = int(os.getenv("N_CTX", "1024"))
N_THREADS = int(os.getenv("N_THREADS", "1"))
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"

# Estado global
_LLM = None
_MODEL_ERROR = None


def download_model_if_needed(model_path: str, model_url: str) -> bool:
    """
    Descarga el modelo automáticamente si no existe.
    CRÍTICO para entornos serverless como Leapcell donde el filesystem es efímero.
    
    Args:
        model_path: Ruta donde debe estar el modelo
        model_url: URL de descarga del modelo
        
    Returns:
        True si el modelo existe o se descargó exitosamente, False si falla
    """
    model_file = Path(model_path)
    
    # Si ya existe, no hacer nada
    if model_file.exists():
        print(f"✅ Modelo encontrado en: {model_path}")
        return True
    
    print(f"⚠️  Modelo NO encontrado en: {model_path}")
    print(f"⬇️  Iniciando descarga automática desde: {model_url}")
    print(f"📦 Tamaño aproximado: ~400 MB")
    
    try:
        # Crear directorio si no existe
        model_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Descargar con urllib (no requiere dependencias extra)
        print("🔄 Descargando... (esto puede tardar varios minutos)")
        
        # Descargar con progreso
        last_percent = -1
        def report_progress(block_num, block_size, total_size):
            nonlocal last_percent
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded * 100) // total_size)
                # Mostrar progreso cada 10%
                if percent >= last_percent + 10:
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"   {percent}% - {mb_downloaded:.1f}/{mb_total:.1f} MB")
                    last_percent = percent
        
        urllib.request.urlretrieve(model_url, model_path, reporthook=report_progress)
        
        print(f"✅ Modelo descargado exitosamente en: {model_path}")
        print(f"📊 Tamaño del archivo: {model_file.stat().st_size / (1024*1024):.1f} MB")
        return True
        
    except urllib.error.URLError as e:
        error_msg = f"❌ Error de red al descargar modelo: {str(e)}"
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"❌ Error inesperado al descargar modelo: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return False


def load_model():
    """Carga el modelo. Si falla, guarda el error."""
    global _LLM, _MODEL_ERROR
    
    print("=" * 60)
    print("🔄 CARGANDO MODELO LLM...")
    print(f"📁 Ruta: {MODEL_PATH}")
    print("=" * 60)
    
    # Intentar descargar si no existe (crítico para serverless)
    if not download_model_if_needed(MODEL_PATH, MODEL_URL):
        error_msg = f"❌ ERROR: No se pudo obtener el modelo en: {MODEL_PATH}"
        print(error_msg)
        _MODEL_ERROR = error_msg
        return False
    
    print("✅ Archivo del modelo disponible")
    
    # Intentar cargar
    try:
        print(f"⚙️  Configuración: n_ctx={N_CTX}, n_threads={N_THREADS}")
        _LLM = Llama(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_threads=N_THREADS,
        )
        print("✅ Modelo cargado exitosamente")
        print("=" * 60)
        return True
    except Exception as e:
        error_msg = f"❌ ERROR cargando modelo: {str(e)}"
        print(error_msg)
        print("=" * 60)
        _MODEL_ERROR = error_msg
        return False


# ⚠️ CARGAR MODELO AQUÍ (se ejecuta al importar el módulo, ANTES de gunicorn)
print("🚀 Inicializando módulo model_api...")
load_model()


@app.get("/")
def root():
    """Información del servicio"""
    if _MODEL_ERROR:
        return jsonify({
            "service": "Agricultural LLM API",
            "status": "error",
            "error": _MODEL_ERROR,
            "model_loaded": False,
            "model_path": MODEL_PATH
        }), 500
    
    return jsonify({
        "service": "Agricultural LLM API",
        "version": "1.0.0",
        "status": "ready",
        "model_loaded": _LLM is not None,
        "model_path": MODEL_PATH,
        "endpoints": {
            "health": "/health",
            "chat": "/chat (POST)"
        }
    })


@app.get("/health")
def health():
    """Health check - FALLA si no hay modelo"""
    if _MODEL_ERROR:
        return jsonify({
            "status": "error",
            "error": _MODEL_ERROR,
            "model_loaded": False,
            "model_path": MODEL_PATH
        }), 500
    
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": _LLM is not None,
        "model_path": MODEL_PATH
    })


@app.post("/chat")
def chat():
    """Endpoint principal - REQUIERE modelo o falla
    
    Con el modelo Qwen 0.5B, las respuestas son más rápidas (1-3 segundos típicamente).
    """
    
    # Si hay error de modelo, retornar error inmediatamente
    if _MODEL_ERROR:
        return jsonify({
            "error": "Model not available",
            "details": _MODEL_ERROR,
            "model_path": MODEL_PATH
        }), 503
    
    # Si no hay modelo cargado (no debería pasar)
    if _LLM is None:
        return jsonify({
            "error": "Model not loaded",
            "details": "LLM instance is None",
            "model_path": MODEL_PATH
        }), 503
    
    try:
        # Parsear request
        payload = request.get_json(force=True)
        system_prompt = payload.get("system", "Eres un asistente agrónomo.")
        context = payload.get("context", {})
        max_tokens = int(payload.get("max_tokens", 256))
        
        mensaje = context.get("mensaje", "")
        print(f"📨 Request: {mensaje[:100]}...")
        
        # Preparar mensajes
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]
        
        # Generar respuesta con el modelo REAL
        print("🤖 Generando respuesta...")
        response = _LLM.create_chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        
        content = response["choices"][0]["message"]["content"] or ""
        print(f"✅ Respuesta: {len(content)} chars")
        
        return jsonify({
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "model": "llama-cpp",
            "tokens": len(content.split())
        })
        
    except Exception as e:
        error_msg = f"Error procesando request: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": error_msg,
            "type": type(e).__name__
        }), 500


if __name__ == "__main__":
    # Este bloque SOLO se ejecuta si corres: python model_api.py
    # NO se ejecuta con gunicorn
    port = int(os.getenv("PORT", 8080))
    print(f"🌐 Ejecutando con Flask dev server en puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
