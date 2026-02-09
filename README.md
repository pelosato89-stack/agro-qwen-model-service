# Servicio 1: Model API (LLM)

## 📋 Descripción
API Flask dedicada exclusivamente a inferencia del modelo de lenguaje (LLM).

## 🔧 Características
- Framework: Flask
- Modelo: llama-cpp-python con GGUF
- Puerto: 8001
- Tipo: **Serverless OK** ✅

## 📦 Dependencias
```bash
pip install -r requirements.txt
```

## 🚀 Ejecución Local
```bash
# Descargar modelo GGUF (si no lo tienes)
mkdir -p models
wget -O models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf

# Configurar variables de entorno
export LOCAL_MODEL_PATH=./models/qwen2.5-0.5b-instruct-q4_k_m.gguf
export N_CTX=1024
export N_THREADS=1

# Ejecutar
python model_api.py
```

## 🔧 Ejecución con Gunicorn (Producción)
```bash
# Opción 1: Usando el script de descarga automática
./download_model.sh gunicorn -c gunicorn.conf.py model_api:app

# Opción 2: Si ya tienes el modelo descargado
gunicorn -c gunicorn.conf.py model_api:app
```

La configuración de Gunicorn incluye:
- 1 worker (para no duplicar modelo en RAM)
- Timeout de 45s (modelo 0.5B es muy rápido: 1-3s)
- Pre-carga del modelo antes de fork
- Reinicio automático cada 200 requests

## 🐳 Ejecución con Docker
```bash
# Instalar dependencias y descargar modelo
apt-get update && \
apt-get install -y curl build-essential cmake && \
rm -rf /var/lib/apt/lists/* && \
mkdir -p models && \
curl -L -o models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf && \
pip install -r requirements.txt

# Iniciar con Gunicorn
gunicorn -c gunicorn.conf.py model_api:app
```

**Nota:** 
- Con `python model_api.py` el servicio usa puerto **8001** (desarrollo)
- Con `gunicorn` el servicio usa puerto **8080** (producción)

El servicio estará disponible en `http://localhost:8001` (dev) o `http://localhost:8080` (gunicorn)

## 🌐 Variables de Entorno

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `LOCAL_MODEL_PATH` | Ruta al archivo GGUF | `./models/qwen2.5-0.5b-instruct-q4_k_m.gguf` |
| `N_CTX` | Tamaño del contexto | `1024` |
| `N_THREADS` | Número de threads CPU | `1` |
| `PORT` | Puerto del servicio | `8001` (dev) / `8080` (gunicorn) |

## 📡 Endpoints

### GET /health
Health check del servicio.

**Response:**
```json
{
  "status": "ok"
}
```

### POST /chat
Inferencia del modelo LLM.

**Request:**
```json
{
  "system": "Eres un asistente agrónomo...",
  "context": {
    "mensaje": "¿Cuándo debo regar?",
    "productor": {...}
  },
  "max_tokens": 256
}
```

**Response:**
```json
{
  "content": "{\"role\": \"consulta\", \"respuesta_chat\": \"...\", ...}"
}
```

## 🚢 Despliegue en Leapcell

### Paso 1: Crear Proyecto
1. Ir a [Leapcell](https://leapcell.io)
2. New Project → Connect GitHub
3. Seleccionar este repositorio
4. Root Directory: `service-1-model`

### Paso 2: Configuración
```
Build Command: pip install -r requirements.txt
Start Command: python model_api.py
Port: 8001
```

### Paso 3: Variables de Entorno
Configurar en el panel de Leapcell:
```
LOCAL_MODEL_PATH=/app/models/qwen2.5-0.5b-instruct-q4_k_m.gguf
N_CTX=1024
N_THREADS=1
```

### Paso 4: Despliegue Automático con Auto-descarga
⚠️ **IMPORTANTE**: El modelo pesa ~400 MB

**El servicio ahora incluye auto-descarga automática del modelo** si no existe en la ruta especificada. Esto es crítico para entornos serverless como Leapcell donde el filesystem es efímero.

**Opciones de despliegue:**

1. **Auto-descarga en cold start** (recomendado para serverless)
   - El modelo se descarga automáticamente la primera vez
   - Usar `/tmp/models/` como ruta de modelo para Leapcell
   - Nota: El primer cold start será más lento (~30-60 segundos)
   - Configurar `LOCAL_MODEL_PATH=/tmp/models/qwen2.5-0.5b-instruct-q4_k_m.gguf`

2. **Volumen persistente** (mejor rendimiento)
   - Crear volumen en Leapcell
   - Montar en `/app/models`
   - Subir archivo GGUF manualmente o dejar que se descargue una vez
   - El modelo persiste entre reinicios

3. **Build con modelo incluido**
   - Incluir modelo en imagen Docker
   - Más pesado pero garantiza disponibilidad

### Paso 5: Deploy
1. Click en Deploy
2. Esperar build (puede tardar por el modelo)
3. Verificar logs
4. Anotar URL: `https://tu-servicio-1.leapcell.dev`

### Paso 6: Probar
```bash
curl https://tu-servicio-1.leapcell.dev/health
# {"status": "ok"}

curl -X POST https://tu-servicio-1.leapcell.dev/chat \
  -H "Content-Type: application/json" \
  -d '{
    "system": "Responde brevemente",
    "context": {"pregunta": "Hola"},
    "max_tokens": 50
  }'
```

## ⚠️ Consideraciones

### Serverless
- **El modelo ahora se descarga automáticamente** si no existe en la ruta especificada
- El modelo se carga en cada cold start
- Primera request será más lenta (5-60 segundos si descarga el modelo, 5-30 segundos si ya está descargado)
- Requests subsecuentes serán muy rápidas (1-3 segundos) si el contenedor está caliente

### Recursos
- **RAM**: Mínimo 512 MB para Qwen 0.5B (más ligero que 1.5B)
- **CPU**: 1 core mínimo (más es mejor)
- **Storage**: ~500 MB para el modelo (antes era 1-2 GB)

### Optimización
- Usar modelo cuantizado Q4_K_M (ya incluido)
- Reducir N_CTX si hay problemas de memoria (ya configurado a 1024)
- Considerar keep-alive para evitar cold starts
- Usar volumen persistente para evitar re-descargas

## 🔗 Integración con Otros Servicios
Este servicio debe ser llamado por el Servicio 2 (Backend).

URL del Servicio 1 debe configurarse en Servicio 2:
```bash
MODEL_API_URL=https://tu-servicio-1.leapcell.dev
```

## 📊 Monitoreo
- Ver logs en panel de Leapcell
- Endpoint `/health` para health checks
- Monitorear tiempo de respuesta (primera request lenta es normal)

## 🐛 Troubleshooting

### Error: "No se encontró el modelo"
- **Solución**: El servicio ahora descarga automáticamente el modelo si no existe
- Verificar que hay acceso a internet para descargar desde HuggingFace
- Verificar `LOCAL_MODEL_PATH` apunta a una ubicación con permisos de escritura
- En Leapcell, usar `/tmp/models/` como ruta
- Asegurar suficiente espacio en disco (~500 MB)

### Error: "Out of memory"
- Reducir `N_CTX` (ya reducido a 1024, puedes probar con 512)
- El modelo 0.5B usa menos RAM que 1.5B (~512 MB vs ~1 GB)
- Aumentar RAM en plan de Leapcell si es necesario

### Cold start muy lento
- Normal en serverless
- Considerar keep-alive o usar servicio persistente
- Optimizar: pre-cargar modelo en memoria compartida (avanzado)

## 📚 Referencias
- [llama-cpp-python docs](https://github.com/abetlen/llama-cpp-python)
- [Modelos GGUF](https://huggingface.co/models?library=gguf)
- [Leapcell docs](https://docs.leapcell.io)
