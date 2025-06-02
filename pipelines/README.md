# Kestra Pipelines para Análisis de Competidores

Este directorio contiene los pipelines de Kestra que automatizan el proceso de análisis de competidores cuando se crean o actualizan modelos de negocio.

## 📋 Resumen

El sistema está diseñado para:

1. **Detectar automáticamente** cuando se crea o actualiza un registro en la tabla `business_models`
2. **Validar** que el modelo de negocio tiene los campos requeridos (`industry`, `customer_persona`)
3. **Triggear automáticamente** el análisis de competidores a través del endpoint interno
4. **Evitar duplicados** verificando si ya existe un análisis en progreso
5. **Proporcionar monitoreo** y logs detallados del proceso

## 🏗️ Arquitectura

```
Frontend -> business_brief.py -> BusinessModel (DB) -> Kestra Pipeline -> analyze_competitors (Internal) -> Competitor Analysis
```

### Componentes principales:

- **business_brief.py**: Endpoint que crea/actualiza el BusinessModel
- **Kestra Pipeline**: Monitora la base de datos y dispara análisis
- **analyze_competitors**: Endpoint interno (sin autenticación) que lee desde DB
- **Controller de análisis**: Ejecuta el análisis de competidores en background

## 📁 Archivos

### 1. `business-model-trigger.yml`
Pipeline básico que:
- Verifica cada 2 minutos por modelos nuevos/actualizados
- Dispara análisis de competidores via endpoint interno

### 2. `business-model-advanced-trigger.yml` ⭐ RECOMENDADO
Pipeline avanzado con:
- Control de concurrencia (máximo 3 análisis simultáneos)
- Verificación de análisis existentes
- Manejo de errores robusto
- Múltiples triggers (schedule, webhook, manual)
- Reportes detallados

## ⚙️ Configuración

### 1. Configuración de Base de Datos en Kestra

El pipeline asume que Kestra puede conectarse a tu base de datos PostgreSQL. Asegúrate de que la configuración en `docker-compose_local.yml` esté correcta:

```yaml
kestra:
  environment:
    KESTRA_CONFIGURATION: |
      datasources:
        postgres:
          url: jdbc:postgresql://postgres:5432/kestra
          username: kestra
          password: k3str4
```

### 2. Endpoint Interno

El sistema usa el endpoint modificado:

- `POST /api/v1/analyze-competitors/{business_id}` - **Uso interno solamente** (sin autenticación)

### 3. Variables de Entorno

El sistema usa estas variables de entorno desde `app/core/config.py`:

```python
POSTGRES_SERVER
POSTGRES_USER  
POSTGRES_PORT
POSTGRES_PASSWORD
POSTGRES_DB
```

## 🚀 Despliegue

### 1. Subir el Flow a Kestra

```bash
# Usando Kestra CLI
kestra flow namespace update business.understanding pipelines/business-model-advanced-trigger.yml

# O via UI en http://localhost:8080
```

### 2. Activar el Pipeline

El pipeline se activará automáticamente con estos triggers:

- **Schedule**: Cada 2 minutos
- **Webhook**: `http://localhost:8080/api/v1/executions/webhook/business.understanding/business-model-advanced-trigger/business_model_webhook_key`
- **Manual**: Via UI de Kestra

### 3. Verificar Configuración

```bash
# Verificar conexión a la base de datos
curl -X POST http://localhost:8080/api/v1/executions/business.understanding/business-model-advanced-trigger \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"check_interval_minutes": 60, "max_concurrent_analysis": 1}}'
```

## 🔧 Modificaciones al Código

### 1. analyze_competitors (business_competitors.py)

**CAMBIO PRINCIPAL:** Convertido a endpoint interno:
- ❌ **Removida autenticación** (no requiere `current_user`)
- ✅ **Lee desde base de datos** como fuente primaria
- ✅ **Fallback a MinIO** para compatibilidad
- ✅ **Nuevo modelo de request** `InternalCompetitorAnalysisRequest`
- ✅ **Tracking de origen** con `triggered_by`

```python
# Antes (para frontend):
current_user: User = Depends(deps.get_current_user)
request: CompetitorAnalysisRequest

# Ahora (para uso interno):
request: Optional[InternalCompetitorAnalysisRequest] = None
# Sin autenticación requerida
```

### 2. Eliminación de webhook separado

- ❌ **Eliminado** `kestra_webhook.py` (duplicación innecesaria)
- ✅ **Simplificado** a un solo endpoint interno

## 📊 Monitoreo

### Logs en Kestra UI

1. Ve a `http://localhost:8080`
2. Busca el namespace `business.understanding`
3. Revisa las ejecuciones del flow `business-model-advanced-trigger`

### Verificar Estado de Análisis

```bash
# Listar investigaciones para un business_id
curl http://localhost:8000/api/v1/analyze-competitors/list-researches/{business_id}

# Verificar estado específico
curl http://localhost:8000/api/v1/analyze-competitors/status/{request_id}
```

### Llamar el endpoint interno manualmente (para testing)

```bash
# Test del endpoint interno
curl -X POST http://localhost:8000/api/v1/analyze-competitors/{business_id} \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "test-business-id",
    "language": "es",
    "research_model": "gpt-4",
    "search_prompt": "Test análisis",
    "base_url": "http://localhost:8000",
    "triggered_by": "manual_test"
  }'
```

## 🐛 Troubleshooting

### Pipeline no se ejecuta

1. Verificar que Kestra esté ejecutándose: `http://localhost:8080`
2. Verificar logs de Kestra: `docker logs noit_backend-kestra-1`
3. Verificar conexión a DB en la tarea `check_database_connection`

### No encuentra modelos de negocio

1. Verificar que la tabla `business_models` existe
2. Verificar que los registros tienen `industry` y `customer_persona` no nulos
3. Revisar el query SQL en la tarea `check_new_business_models`

### Endpoint interno falla

1. Verificar que el endpoint esté disponible: `curl http://localhost:8000/api/v1/analyze-competitors/test-id`
2. Revisar logs de FastAPI: `docker logs noit_backend-web-1`
3. Verificar que no hay errores de importación tras los cambios

### Análisis no se ejecuta

1. Verificar que no hay análisis pendientes: `SELECT * FROM competitor_research WHERE status = 'PENDING'`
2. Revisar logs del controller de análisis de competidores
3. Verificar configuración de MinIO y servicios externos

## 📈 Optimizaciones

### Para Producción

1. **Rate Limiting**: Limitar frecuencia de ejecución del endpoint interno
2. **Secrets**: Usar Kestra secrets para credenciales de DB
3. **Monitoring**: Integrar con sistemas de monitoreo (Prometheus, etc.)
4. **Scaling**: Configurar workers de Kestra para mayor throughput
5. **Autenticación interna**: Agregar API key para el endpoint interno

### Configuración Secrets en Kestra

```yaml
# En el flow, reemplazar credenciales hardcoded:
url: "jdbc:postgresql://{{ secret('DB_HOST') }}:{{ secret('DB_PORT') }}/{{ secret('DB_NAME') }}"
username: "{{ secret('DB_USER') }}"
password: "{{ secret('DB_PASSWORD') }}"
```

## 🔄 Flujo Completo

1. **Usuario completa brief** en frontend
2. **business_brief.py** crea/actualiza `BusinessModel` en DB
3. **Kestra pipeline** detecta el cambio (cada 2 min o via webhook)
4. **Pipeline valida** que el modelo tiene campos requeridos
5. **Pipeline llama** al endpoint interno `analyze_competitors`
6. **Endpoint interno** inicia análisis en background (sin autenticación)
7. **Análisis se ejecuta** y guarda resultados en MinIO
8. **Usuario puede ver** resultados via endpoints de consulta

## 🚧 Próximos Pasos

1. Implementar notificaciones (email/Slack) cuando el análisis termine
2. Agregar webhook desde business_brief.py para trigger inmediato
3. Crear dashboard de monitoreo para análisis en progreso
4. Implementar retry automático para análisis fallidos
5. Agregar métricas de performance y tiempo de ejecución
6. Considerar API key para endpoint interno en producción 