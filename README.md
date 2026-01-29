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
wget -O models/qwen2.5-3b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf

# Configurar variables de entorno
export LOCAL_MODEL_PATH=./models/qwen2.5-3b-instruct-q4_k_m.gguf
export N_CTX=2048
export N_THREADS=1

# Ejecutar
python model_api.py
```

El servicio estará disponible en `http://localhost:8001`

## 🌐 Variables de Entorno

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `LOCAL_MODEL_PATH` | Ruta al archivo GGUF | `./models/qwen2.5-3b-instruct-q4_k_m.gguf` |
| `N_CTX` | Tamaño del contexto | `2048` |
| `N_THREADS` | Número de threads CPU | `1` |
| `PORT` | Puerto del servicio | `8001` |

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
  "max_tokens": 300
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
LOCAL_MODEL_PATH=/app/models/qwen2.5-3b-instruct-q4_k_m.gguf
N_CTX=2048
N_THREADS=1
```

### Paso 4: Subir Modelo GGUF
⚠️ **IMPORTANTE**: El modelo pesa 3-4 GB

Opciones:
1. **Volumen persistente** (recomendado)
   - Crear volumen en Leapcell
   - Montar en `/app/models`
   - Subir archivo GGUF

2. **Descargar en build**
   - Crear script de inicio que descargue el modelo
   - Cachear en volumen

3. **Build con modelo incluido**
   - Incluir modelo en imagen Docker (muy pesado)

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
- El modelo se carga en cada cold start
- Primera request será lenta (5-30 segundos)
- Requests subsecuentes serán más rápidas si el contenedor está caliente

### Recursos
- **RAM**: Mínimo 2 GB para Qwen 3B
- **CPU**: 1 core mínimo (más es mejor)
- **Storage**: 4-5 GB para el modelo

### Optimización
- Usar modelo cuantizado (Q4_K_M es buena opción)
- Reducir N_CTX si hay problemas de memoria
- Considerar keep-alive para evitar cold starts

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
- Verificar `LOCAL_MODEL_PATH`
- Asegurar que el modelo existe en el volumen

### Error: "Out of memory"
- Reducir `N_CTX`
- Usar modelo más pequeño (1.5B en vez de 3B)
- Aumentar RAM en plan de Leapcell

### Cold start muy lento
- Normal en serverless
- Considerar keep-alive o usar servicio persistente
- Optimizar: pre-cargar modelo en memoria compartida (avanzado)

## 📚 Referencias
- [llama-cpp-python docs](https://github.com/abetlen/llama-cpp-python)
- [Modelos GGUF](https://huggingface.co/models?library=gguf)
- [Leapcell docs](https://docs.leapcell.io)
