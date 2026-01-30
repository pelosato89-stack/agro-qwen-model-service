"""
Configuración Gunicorn optimizada para velocidad con LLM pequeño
"""

bind = "0.0.0.0:8080"

# Solo 1 worker para no duplicar modelo en RAM
workers = 1
worker_class = "sync"

# Timeout más corto ahora que el modelo es rápido
timeout = 60  # 1 minuto (modelo 1.5B responde en 3-8s)
graceful_timeout = 30
keepalive = 5

# Pre-cargar modelo ANTES de fork
preload_app = True

# Reiniciar worker cada 200 requests para liberar memoria
max_requests = 200
max_requests_jitter = 20

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

print("=" * 60)
print("🔧 Gunicorn Config Optimizada:")
print(f"   Workers: {workers}")
print(f"   Timeout: {timeout}s")
print(f"   Max Requests: {max_requests}")
print(f"   Preload: {preload_app}")
print("=" * 60)
