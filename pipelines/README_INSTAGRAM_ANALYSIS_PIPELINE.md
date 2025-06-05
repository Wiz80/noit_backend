# 🚀 Instagram Analysis Complete Pipeline - Kestra

Este pipeline ejecuta un análisis completo de Instagram en secuencia después de que el pipeline de extracción de redes sociales haya completado exitosamente.

## 📋 Descripción General

El pipeline **`instagram-analysis-complete-trigger`** se encarga de:

1. **Detectar competidores** con URLs de Instagram recién actualizadas
2. **Ejecutar análisis secuencial** de Instagram en 4 pasos:
   - Scraping inicial de Instagram
   - Análisis de comentarios (categorización, sentimiento, topics)
   - Análisis de imágenes (OpenAI Vision)
   - Generación de estadísticas
3. **Monitorear progreso** y manejar errores de cada paso
4. **Generar reportes** detallados de éxito/falla por competidor

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Social Media  │    │   Instagram     │    │   4 Analysis    │
│   Extraction    │───▶│   Analysis      │───▶│   Steps         │
│   Pipeline      │    │   Pipeline      │    │                 │
│                 │    │                 │    │ 1. Scraping     │
│ Webhook trigger │    │ Sequential      │    │ 2. Comments     │
│ on completion   │    │ Processing      │    │ 3. Images       │
│                 │    │                 │    │ 4. Statistics   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 Flujo de Análisis Secuencial

Para cada competidor con Instagram URL:

### Paso 1: Scraping Inicial de Instagram
```
POST /api/v1/business/competitive-analysis/instagram/{business_id}
```
- Extrae posts e información del perfil
- Guarda datos en MinIO y base de datos
- **Tiempo estimado**: 5-10 minutos

### Paso 2: Análisis de Comentarios  
```
POST /api/v1/business/competitive-analysis/instagram/{business_id}/complete-comments-analysis
```
- Categorización usando LLM (OpenAI GPT-4o-mini)
- Análisis de sentimiento (spaCy)
- Modelado de temas (LDA)
- **Tiempo estimado**: 5-15 minutos

### Paso 3: Análisis de Imágenes
```
POST /api/v1/business/competitive-analysis/instagram/{business_id}/complete-image-analysis
```
- Análisis de imágenes usando OpenAI Vision API
- Coherencia visual del feed
- Patrones de contenido visual
- **Tiempo estimado**: 10-20 minutos

### Paso 4: Generación de Estadísticas
```
POST /api/v1/business/competitive-analysis/instagram/{business_id}/complete-statistics-analysis
```
- Métricas de engagement
- Patrones de publicación
- Estadísticas de audiencia
- **Tiempo estimado**: 2-5 minutos

## 🔧 Componentes del Pipeline

### 1. **Triggers (Disparadores)**

#### Social Media Completion Trigger (Principal)
```yaml
webhook_key: "instagram_analysis_after_social_media"
condition: "{{ trigger.body.event == 'social_media_extraction_completed' }}"
```

#### Manual Trigger
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/instagram-analysis-complete-trigger/instagram_analysis_manual \
  -H "Content-Type: application/json" \
  -d '{"action": "trigger_instagram_analysis"}'
```

#### Schedule Trigger
```yaml
cron: "0 */2 * * *"  # Cada 2 horas
```

### 2. **Query de Detección de Competidores**

Busca competidores que:
- ✅ Tienen URL de Instagram válida
- ✅ Fueron actualizados recientemente (últimas 6 horas)
- ✅ URL contiene 'instagram.com'
- ✅ Extrae automáticamente el username de Instagram

```sql
SELECT 
  c.id as competitor_id,
  c.business_idea_id,
  c.competitor_name,
  c.instagram_url,
  REGEXP_REPLACE(c.instagram_url, '^https?://(?:www\.)?instagram\.com/([^/?]+).*$', '\1') as instagram_username,
  bi.title as business_title
FROM competitors c
LEFT JOIN business_ideas bi ON c.business_idea_id = bi.id
WHERE c.instagram_url IS NOT NULL 
  AND c.instagram_url != ''
  AND c.instagram_url LIKE '%instagram.com%'
  AND (c.updated_at > NOW() - INTERVAL '6 hours' OR c.created_at > NOW() - INTERVAL '6 hours')
ORDER BY c.updated_at DESC
LIMIT 10;
```

### 3. **Procesamiento Secuencial**

Para cada competidor:
1. **Log inicio** del análisis 
2. **Paso 1**: Instagram scraping inicial
3. **Wait**: Tiempo de espera para completar Step 1
4. **Paso 2**: Análisis de comentarios
5. **Paso 3**: Análisis de imágenes
6. **Paso 4**: Generación de estadísticas
7. **Summary**: Resumen de éxito/falla por paso
8. **Log completion** con métricas finales

## 🎯 Parámetros de Configuración

### Inputs del Pipeline

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `business_id` | STRING | null | ID específico de negocio (opcional) |
| `competitor_ids` | ARRAY | null | IDs específicos de competidores (opcional) |
| `triggered_by` | STRING | "social_media_extraction" | Fuente que disparó el pipeline |
| `max_concurrent_analysis` | INT | 2 | Máximo análisis concurrentes |
| `wait_timeout_minutes` | INT | 30 | Timeout por cada paso de análisis |

### Personalización de Parámetros por Paso

#### Paso 2: Comentarios
```json
{
  "num_topics": 5,
  "max_comments": 100,
  "provider": "openai",
  "model": "openai:gpt-4o-mini",
  "lang": "es",
  "run_in_background": true
}
```

#### Paso 3: Imágenes
```json
{
  "posts_limit": 20,
  "run_in_background": true
}
```

#### Paso 4: Estadísticas
```json
{
  "post_limit": 50,
  "image_limit": 10,
  "run_in_background": true
}
```

## 📊 Monitoreo y Logs

### Dashboard de Kestra
- **URL**: http://localhost:8080
- **Namespace**: `noit.backend`
- **Flow**: `instagram-analysis-complete-trigger`

### Tipos de Logs por Etapa

#### 🚀 Inicio del Pipeline
```
🚀 Starting Complete Instagram Analysis Pipeline
Business ID: Auto-detect from recent updates
Triggered by: social_media_extraction_completion
Max concurrent: 2
Timeout: 30 minutes
```

#### 📱 Inicio de Competidor
```
📱 Starting Instagram analysis for competitor: Competitor Name
Business: Business Title
Instagram: https://instagram.com/username
Username: username
Business ID: business-uuid
Competitor ID: competitor-uuid
```

#### ✅ Éxito por Paso
```
🔍 Step 1 - Instagram analysis response for Competitor Name:
Status Code: 200
✅ Step 1 SUCCESS - Task ID: task-uuid-here
```

#### ❌ Error por Paso
```
🔍 Step 2 - Comments analysis response for Competitor Name (@username):
Status Code: 500
❌ Step 2 FAILED - Error: Instagram user username not found
```

#### 📊 Resumen por Competidor
```
📊 Analysis Summary for Competitor Name (@username):
   Success Rate: 75.0% (3/4)
   Overall Status: PARTIAL
   step1: ✅ SUCCESS
   step2: ✅ SUCCESS  
   step3: ✅ SUCCESS
   step4: ❌ FAILED
```

### Reporte Final

```json
{
  "pipeline": "instagram-analysis-complete",
  "execution_time": "2024-01-15T15:30:00.000Z",
  "triggered_by": "social_media_extraction_completion",
  "total_competitors_found": 3,
  "business_id": "auto-detected",
  "competitors_processed": [
    {
      "competitor_id": "uuid-1",
      "competitor_name": "Competitor 1",
      "instagram_username": "competitor1",
      "instagram_url": "https://instagram.com/competitor1",
      "business_title": "My Business",
      "business_id": "business-uuid"
    }
  ],
  "configuration": {
    "max_concurrent_analysis": 2,
    "wait_timeout_minutes": 30
  }
}
```

## ⚙️ Configuración y Despliegue

### 1. Subir el Pipeline a Kestra

```bash
# Via API
curl -X PUT http://localhost:8080/api/v1/flows/noit.backend/instagram-analysis-complete-trigger \
  -H "Content-Type: application/yaml" \
  --data-binary @pipelines/instagram-analysis-complete-trigger.yml
```

### 2. Verificar Triggers

```bash
# Verificar webhook
curl http://localhost:8080/api/v1/flows/noit.backend/instagram-analysis-complete-trigger/triggers
```

### 3. Probar Manualmente

```bash
# Trigger manual con business específico
curl -X POST http://localhost:8080/api/v1/executions/noit.backend/instagram-analysis-complete-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "business_id": "your-business-id",
      "triggered_by": "manual_test",
      "max_concurrent_analysis": 1,
      "wait_timeout_minutes": 20
    }
  }'
```

## 🔄 Integración con Social Media Pipeline

### Modificación del Pipeline Anterior

El pipeline `social-media-extraction-trigger` fue modificado para incluir al final:

```yaml
- id: trigger_instagram_analysis
  type: io.kestra.plugin.core.http.Request
  uri: "http://localhost:8080/api/v1/executions/webhook/noit.backend/instagram-analysis-complete-trigger/instagram_analysis_after_social_media"
  method: "POST"
  body: |
    {
      "event": "social_media_extraction_completed",
      "source_pipeline": "social-media-extraction-trigger",
      "competitors_processed": {{ outputs.find_competitors_needing_social_media.rows | length }},
      "inputs": {
        "triggered_by": "social_media_extraction_completion",
        "max_concurrent_analysis": 2,
        "wait_timeout_minutes": 30
      }
    }
```

### Flujo Completo Integrado

1. **Pipeline 1**: `social-media-extraction-trigger`
   - Detecta competidores nuevos
   - Extrae redes sociales de sitios web
   - **Al terminar** → Dispara Pipeline 2

2. **Pipeline 2**: `instagram-analysis-complete-trigger`  
   - Detecta competidores con Instagram
   - Ejecuta análisis completo en 4 pasos
   - Genera reportes finales

## 🛠️ Troubleshooting

### Pipeline no se ejecuta automáticamente

1. **Verificar webhook del pipeline anterior**:
   ```bash
   # Revisar logs del task trigger_instagram_analysis en social-media-extraction
   ```

2. **Verificar trigger configuration**:
   ```bash
   curl http://localhost:8080/api/v1/flows/noit.backend/instagram-analysis-complete-trigger/triggers
   ```

### Pasos fallan frecuentemente

1. **Verificar endpoints FastAPI**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verificar TaskIQ workers**:
   ```bash
   docker logs noit_backend-taskiq-worker-1
   ```

3. **Verificar OpenAI API key** (para análisis de imágenes):
   ```bash
   echo $OPENAI_API_KEY
   ```

### Timeouts en análisis

1. **Aumentar timeout**:
   ```json
   {
     "inputs": {
       "wait_timeout_minutes": 60
     }
   }
   ```

2. **Reducir límites de datos**:
   - Comments: `max_comments: 50`
   - Images: `posts_limit: 10`
   - Statistics: `post_limit: 20`

### No encuentra competidores con Instagram

1. **Verificar datos recientes**:
   ```sql
   SELECT * FROM competitors 
   WHERE instagram_url IS NOT NULL 
   AND updated_at > NOW() - INTERVAL '6 hours';
   ```

2. **Verificar formato de URLs**:
   ```sql
   SELECT instagram_url FROM competitors 
   WHERE instagram_url LIKE '%instagram.com%';
   ```

## 📈 Optimizaciones

### Para Producción

1. **Parallelization**: Usar `EachParallel` en lugar de `EachSequential`
2. **Intelligent Retry**: Agregar reintentos automáticos por paso
3. **Resource Management**: Configurar límites de CPU/memoria
4. **Cost Control**: Limitar uso de OpenAI API por día
5. **Progress Polling**: Implementar polling real de task status

### Configuración Avanzada

```yaml
inputs:
  - id: retry_attempts
    type: INT
    defaults: 3
  - id: parallel_processing
    type: BOOLEAN  
    defaults: false
  - id: cost_limit_usd
    type: FLOAT
    defaults: 50.0
  - id: notification_webhook
    type: STRING
    defaults: ""
```

### Ejemplo de Paralelización

```yaml
- id: process_instagram_competitors_parallel
  type: io.kestra.plugin.core.flow.EachParallel
  value: "{{ outputs.find_competitors_with_instagram.rows }}"
  concurrent: "{{ inputs.max_concurrent_analysis }}"
```

## 🚧 Próximos Pasos

1. **Real-time Progress Polling**: Implementar polling de progreso real
2. **Intelligent Scheduling**: Ejecutar análisis en horarios de bajo costo
3. **Data Quality Checks**: Validar calidad de datos antes de análisis
4. **Advanced Error Handling**: Retry específico por tipo de error
5. **Performance Metrics**: Métricas de tiempo y costo por análisis
6. **Notification System**: Alertas en Slack/email por completion/falla

## 📚 Enlaces Útiles

- 📖 [Documentación Kestra](https://kestra.io/docs)
- 🔗 [Social Media Pipeline](./README_SOCIAL_MEDIA_PIPELINE.md)
- 📊 [Dashboard Kestra](http://localhost:8080)
- 🎯 [Endpoints de Instagram](../app/api/v1/endpoints/business/competitive_analysis/instagram/)
- 📋 [TaskIQ Documentation](https://taskiq-python.github.io/)

## ⚠️ Consideraciones Importantes

1. **Costo OpenAI**: El análisis de imágenes puede ser costoso
2. **Rate Limits**: Instagram y OpenAI tienen límites de requests
3. **Processing Time**: Análisis completo puede tomar 30-60 minutos
4. **Storage Requirements**: Datos de análisis requieren espacio en MinIO
5. **Monitoring**: Es crítico monitorear el progreso de cada paso 