# 🚀 Deployment Guide - Noit Backend

## 📋 Requisitos

- Docker & Docker Compose
- Certificados SSL (Let's Encrypt)
- Archivo `.env.prod` configurado

## 🔧 Configuraciones Disponibles

### **Desarrollo Local**
```bash
# Levantar stack completo de desarrollo
docker-compose -f docker-compose_local.yml up -d

# Solo FastAPI + TaskIQ
docker-compose -f docker-compose_local.yml up app taskiq-worker redis taskiq-admin

# Ver logs
docker-compose -f docker-compose_local.yml logs -f app taskiq-worker
```

### **Producción**
```bash
# Levantar stack de producción con Nginx
docker-compose -f docker-compose.prod.yml up -d

# Verificar estado
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs nginx
```

## ⚙️ Configuración de Nginx para Producción

### **Características Optimizadas:**

✅ **Load Balancing** - Distribución de carga entre workers de Gunicorn  
✅ **Rate Limiting** - Protección contra DDoS y abuso  
✅ **Compression** - Gzip para mejor performance  
✅ **SSL/TLS** - HTTP/2 + certificados Let's Encrypt  
✅ **Security Headers** - HSTS, XSS Protection, etc.  
✅ **Caching** - Para archivos estáticos  
✅ **Health Checks** - Monitoreo automático  

### **Rutas Configuradas:**

- **`/api/`** - Rate limit: 10 req/s, burst 20
- **`/login|register|auth`** - Rate limit: 1 req/s, burst 5  
- **`/taskiq-admin/`** - Dashboard de TaskIQ (solo staging/dev)
- **`/health`** - Health check endpoint
- **`/`** - Todas las demás rutas de FastAPI

## 🐳 Workers de Gunicorn

### **Configuración Actual:**
```bash
gunicorn app.main:app \
  -w 4 \                          # 4 workers
  -k uvicorn.workers.UvicornWorker \  # Worker async
  --bind 0.0.0.0:8000 \
  --timeout 120 \                 # Timeout 2 minutos
  --keep-alive 5 \                # Keep-alive connections
  --max-requests 1000 \           # Restart worker cada 1000 requests
  --max-requests-jitter 100 \     # Jitter para evitar restart simultáneo
  --preload                       # Precargar aplicación
```

### **TaskIQ Workers:**
```bash
taskiq worker app.tasks.broker:broker \
  --workers 4 \                   # 4 workers por contenedor
  --max-async-tasks 20 \          # 20 tareas concurrentes
  --fs-discover                   # Auto-discover tasks
```

## 🔄 Escalabilidad

### **Horizontal Scaling:**
```yaml
# En docker-compose.prod.yml
deploy:
  replicas: 2  # Múltiples instancias del worker
```

### **Vertical Scaling:**
- Ajustar `-w` en Gunicorn (workers)
- Ajustar `--workers` en TaskIQ
- Ajustar `worker_connections` en Nginx

## 📊 Monitoreo

### **URLs de Acceso:**
- **FastAPI**: https://noit.com.co
- **TaskIQ Admin**: https://noit.com.co/taskiq-admin/ (staging)
- **Health Check**: https://noit.com.co/health

### **Logs:**
```bash
# Nginx logs
docker logs noit_nginx

# FastAPI logs  
docker logs noit_fastapi_app

# TaskIQ Worker logs
docker logs taskiq_worker_prod
```

## 🛡️ Seguridad

### **Headers de Seguridad:**
- `Strict-Transport-Security` - HSTS
- `X-Frame-Options` - Clickjacking protection
- `X-Content-Type-Options` - MIME sniffing protection
- `X-XSS-Protection` - XSS protection
- `Referrer-Policy` - Referrer control

### **Rate Limiting:**
- API general: 10 req/s
- Autenticación: 1 req/s
- Burst permitido según endpoint

## 🔧 Variables de Entorno

### **Crear `.env.prod`:**
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/noit_prod

# Redis
REDIS_URL=redis://redis:6379/0

# TaskIQ
TASKIQ_ADMIN_URL=http://taskiq-admin:3000
TASKIQ_ADMIN_API_TOKEN=your-secret-token
TASKIQ_BROKER_NAME=noit_backend_prod

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Security
SECRET_KEY=your-super-secret-key
ENVIRONMENT=production
```

## 🚀 Deployment Commands

### **Primera vez:**
```bash
# 1. Configurar certificados SSL
./setup-ssl.sh

# 2. Crear archivo de producción
cp .env.example .env.prod
# Editar .env.prod con valores reales

# 3. Build y deploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Verificar
curl -I https://noit.com.co/health
```

### **Updates:**
```bash
# Pull latest changes
git pull origin main

# Rebuild y redeploy
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Verificar rolling update
docker-compose -f docker-compose.prod.yml logs -f app
```

## 🎯 Performance Tips

1. **Ajustar workers según CPU**: `workers = 2 * cores + 1`
2. **Monitorear memoria**: TaskIQ workers pueden consumir RAM
3. **Redis persistence**: Configurar snapshots según necesidades
4. **Nginx buffers**: Ajustar según tamaño de responses
5. **Health checks**: Monitorear `/health` endpoint

## 🔍 Troubleshooting

```bash
# Verificar estado de servicios
docker-compose -f docker-compose.prod.yml ps

# Logs en tiempo real
docker-compose -f docker-compose.prod.yml logs -f

# Reiniciar servicio específico
docker-compose -f docker-compose.prod.yml restart app

# Verificar configuración de Nginx
docker exec noit_nginx nginx -t

# Conectar a Redis
docker exec -it redis redis-cli
``` 