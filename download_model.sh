#!/bin/bash
set -e

MODEL_DIR="${MODEL_DIR:-/app/models}"
MODEL_FILE="${MODEL_FILE:-qwen2.5-1.5b-instruct-q4_k_m.gguf}"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"

echo "============================================================"
echo "🔍 Verificando modelo..."
echo "📁 Directorio: $MODEL_DIR"
echo "📄 Archivo: $MODEL_FILE"
echo "============================================================"

mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
    echo "⬇️  Descargando modelo (~1 GB)..."
    echo "⏱️  Esto puede tardar 5-15 minutos dependiendo de tu conexión"
    echo "📝 Nota: Para producción, se recomienda verificar el checksum del archivo descargado"
    wget -q --show-progress -O "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL"
    echo "✅ Descarga completa"
else
    echo "✅ Modelo ya existe"
    ls -lh "$MODEL_DIR/$MODEL_FILE"
fi

echo "============================================================"
echo "🚀 Iniciando servidor..."
echo "============================================================"
exec "$@"
