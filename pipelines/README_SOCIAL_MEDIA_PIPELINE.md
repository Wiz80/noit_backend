# 🚀 Social Media Extraction Pipeline - Kestra

Este pipeline extrae información de redes sociales de los sitios web de competidores para un business específico mediante webhook.

## 📋 Descripción General

El pipeline **`social-media-extraction-trigger`** se encarga de:

1. **Recibir un business_id** via webhook
2. **Validar** que el business existe en la base de datos
3. **Buscar todos los competidores** de ese business que tengan sitios web
4. **Extraer redes sociales** de cada competidor via TaskIQ
5. **Triggear automáticamente** el pipeline de análisis de Instagram
6. **Generar reportes** detallados del procesamiento

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Webhook       │    │   Kestra        │    │   FastAPI       │    │   TaskIQ        │
│   with          │───▶│   Pipeline      │───▶│   Endpoint      │───▶│   Worker        │
│   business_id   │    │                 │    │                 │    │                 │
│ Manual/API call │    │ Validate & Find │    │ social-media/   │    │ Website         │
│                 │    │ Competitors     │    │ {business_id}   │    │ Scraping        │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 Componentes del Pipeline

### 1. **Triggers (Disparadores)**

#### Primary Webhook Trigger (Principal)
```yaml
webhook_key: "social_media_extraction_by_business"
condition: "{{ trigger.body.business_id is defined }}"
```

**Uso:**
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "your-business-uuid-here",
    "process_all_competitors": true,
    "max_concurrent_extractions": 3
  }'
```

#### Manual Trigger (Legacy)
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_manual \
  -H "Content-Type: application/json" \
  -d '{"action": "trigger_social_media_extraction"}'
```

### 2. **Validación de Business**

El pipeline primero valida que el business_id existe:
```sql
SELECT id, title, description, created_at
FROM business_ideas 
WHERE id = 'business_id'
```

Si no existe, el pipeline falla inmediatamente.

### 3. **Query de Detección de Competidores**

Busca competidores que:
- ✅ Pertenecen al business_id específico
- ✅ Tienen un sitio web válido (`website` no es NULL/vacío)
- ✅ Necesitan extracción (si `process_all_competitors=false`)
- ✅ O todos los competidores (si `process_all_competitors=true`)

```sql
SELECT 
  c.id as competitor_id,
  c.business_idea_id,
  c.competitor_name,
  c.website,
  c.instagram_url,
  c.facebook_url,
  c.linkedin_url,
  c.x_url,
  c.youtube_url,
  c.tiktok_url,
  bi.title as business_title,
  CASE 
    WHEN c.website IS NOT NULL 
      AND c.website != ''
      AND (
        process_all_competitors = true OR
        c.instagram_url IS NULL OR c.instagram_url = '' OR
        c.facebook_url IS NULL OR c.facebook_url = '' OR
        c.linkedin_url IS NULL OR c.linkedin_url = '' OR
        c.x_url IS NULL OR c.x_url = '' OR
        c.youtube_url IS NULL OR c.youtube_url = '' OR
        c.tiktok_url IS NULL OR c.tiktok_url = ''
      )
    THEN true 
    ELSE false 
  END as needs_social_media_extraction
FROM competitors c
LEFT JOIN business_ideas bi ON c.business_idea_id = bi.id
WHERE c.business_idea_id = 'business_id'
  AND c.website IS NOT NULL 
  AND c.website != ''
ORDER BY c.created_at DESC;
```

### 4. **Procesamiento Secuencial por Competidor**

Para cada competidor encontrado:
1. **Log** información del competidor
2. **HTTP Request** al endpoint de extracción individual
3. **Procesamiento** de la respuesta
4. **Log** del resultado final

### 5. **Endpoint de Destino**

```
POST /api/v1/business/competitive-analysis/social-media/{business_id}
```

**Body:**
```json
{
  "update_db": true,
  "competitor_ids": ["competitor-uuid-here"]
}
```

## 🎯 Parámetros de Configuración

### Inputs del Pipeline

| Parámetro | Tipo | Required | Default | Descripción |
|-----------|------|----------|---------|-------------|
| `business_id` | STRING | ✅ Sí | - | ID del business a procesar |
| `max_concurrent_extractions` | INT | ❌ No | 3 | Máximo número de extracciones concurrentes |
| `process_all_competitors` | BOOLEAN | ❌ No | true | Procesar todos los competidores o solo los que necesitan extracción |
| `competitor_ids` | ARRAY | ❌ No | null | IDs específicos de competidores (opcional) |

### Ejemplos de Uso

#### Procesar todos los competidores de un business
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "12345678-1234-1234-1234-123456789012",
    "process_all_competitors": true,
    "max_concurrent_extractions": 5
  }'
```

#### Procesar solo competidores que necesitan extracción
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "12345678-1234-1234-1234-123456789012",
    "process_all_competitors": false
  }'
```

#### Procesar competidores específicos
```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "12345678-1234-1234-1234-123456789012",
    "competitor_ids": [
      "comp-uuid-1",
      "comp-uuid-2"
    ]
  }'
```

#### Ejecución directa (sin webhook)
```bash
curl -X POST http://localhost:8080/api/v1/executions/noit.backend/social-media-extraction-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "business_id": "12345678-1234-1234-1234-123456789012",
      "process_all_competitors": true,
      "max_concurrent_extractions": 3
    }
  }'
```

## 📊 Monitoreo y Logs

### Dashboard de Kestra
- **URL**: http://localhost:8080
- **Namespace**: `noit.backend`
- **Flow**: `social-media-extraction-trigger`

### Tipos de Logs

#### 🚀 Inicio del Pipeline
```
🚀 Starting Social Media Extraction Pipeline
Business ID: 12345678-1234-1234-1234-123456789012
Max concurrent: 3
Process all competitors: true
Specific competitor IDs: None (process all)
```

#### ✅ Validación de Business
```
🔍 Validating business ID: 12345678-1234-1234-1234-123456789012
✅ Business found: My Awesome Business
   ID: 12345678-1234-1234-1234-123456789012
   Description: An innovative business focused on...
   Created: 2024-01-15T10:30:00Z
```

#### 📊 Análisis de Competidores
```
📊 Competitors Analysis for Business: 12345678-1234-1234-1234-123456789012
Process all competitors: true
Total competitors found: 5

🏢 Competitors to process:
1. Competitor ABC
   Website: https://competitor-abc.com
   Needs extraction: ✅ Yes

2. Competitor XYZ
   Website: https://competitor-xyz.com
   Needs extraction: ❌ No
```

#### 📋 Procesamiento Individual
```
📋 Processing competitor: Competitor ABC
Business: My Awesome Business
Website: https://competitor-abc.com
Competitor ID: comp-uuid-1
Business ID: 12345678-1234-1234-1234-123456789012
Needs extraction: true
```

#### ✅ Resultado Exitoso
```
🎯 Completed processing competitor: Competitor ABC

Extraction Result: ✅ SUCCESS

Task ID: task-uuid-here

Competitor Details:
- Name: Competitor ABC
- Website: https://competitor-abc.com
- Business: My Awesome Business
```

### Reporte de Resumen

Al final de cada ejecución:
```json
{
  "execution_time": "2024-01-15T10:30:00.000Z",
  "business_id": "12345678-1234-1234-1234-123456789012",
  "total_competitors_found": 5,
  "process_all_competitors": "true",
  "specific_competitor_ids": null,
  "competitors_processed": [
    {
      "competitor_id": "comp-uuid-1",
      "competitor_name": "Competitor ABC",
      "website": "https://competitor-abc.com",
      "business_title": "My Awesome Business",
      "needs_extraction": true
    }
  ]
}
```

## 🔄 Integración con Instagram Analysis Pipeline

### Trigger Automático

Al completar exitosamente, el pipeline automáticamente dispara el análisis de Instagram:

```yaml
- id: trigger_instagram_analysis
  type: io.kestra.plugin.core.http.Request
  uri: "http://localhost:8080/api/v1/executions/webhook/noit.backend/instagram-analysis-complete-trigger/instagram_analysis_after_social_media"
  body: |
    {
      "event": "social_media_extraction_completed",
      "business_id": "{{ inputs.business_id }}",
      "competitors_processed": 5,
      "inputs": {
        "business_id": "{{ inputs.business_id }}",
        "triggered_by": "social_media_extraction_completion"
      }
    }
```

### Flujo Completo Integrado

1. **API/Webhook Call** → Trigger social media extraction para business_id
2. **Social Media Pipeline** → Procesa todos los competidores del business
3. **Auto-trigger** → Dispara Instagram analysis para el mismo business
4. **Instagram Pipeline** → Análisis completo de Instagram para competidores encontrados

## ⚙️ Configuración y Despliegue

### 1. Subir el Pipeline a Kestra

```bash
# Via API
curl -X PUT http://localhost:8080/api/v1/flows/noit.backend/social-media-extraction-trigger \
  -H "Content-Type: application/yaml" \
  --data-binary @pipelines/social-media-extraction-trigger.yml
```

### 2. Verificar el Pipeline

```bash
# Ver detalles del flow
curl http://localhost:8080/api/v1/flows/noit.backend/social-media-extraction-trigger

# Verificar triggers
curl http://localhost:8080/api/v1/flows/noit.backend/social-media-extraction-trigger/triggers
```

### 3. Testing

```bash
# Test básico con business_id
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "test-business-id",
    "process_all_competitors": false,
    "max_concurrent_extractions": 1
  }'
```

## 🛠️ Troubleshooting

### Pipeline falla inmediatamente

1. **Verificar business_id existe**:
   ```sql
   SELECT * FROM business_ideas WHERE id = 'your-business-id';
   ```

2. **Verificar formato del business_id**:
   - Debe ser un UUID válido
   - No puede ser null o vacío

### No encuentra competidores

1. **Verificar competidores existen**:
   ```sql
   SELECT * FROM competitors 
   WHERE business_idea_id = 'your-business-id'
   AND website IS NOT NULL;
   ```

2. **Verificar parámetro process_all_competitors**:
   - `true`: Procesa todos los competidores con website
   - `false`: Solo procesa los que necesitan extracción

### Endpoint FastAPI falla

1. **Verificar endpoint disponible**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verificar TaskIQ workers**:
   ```bash
   docker logs noit_backend-taskiq-worker-1
   ```

3. **Verificar formato del request**:
   - `update_db` debe ser `true`
   - `competitor_ids` debe ser array con UUIDs válidos

## 📈 Optimizaciones

### Para Producción

1. **Rate Limiting**: Controlar frecuencia entre competidores
2. **Batch Processing**: Procesar múltiples competidores en paralelo
3. **Error Recovery**: Retry automático para fallos temporales
4. **Resource Management**: Limitar uso de CPU/memoria
5. **Monitoring**: Métricas de éxito/falla por business

### Configuración Avanzada

```json
{
  "business_id": "12345678-1234-1234-1234-123456789012",
  "max_concurrent_extractions": 5,
  "process_all_competitors": false,
  "competitor_ids": ["specific-comp-1", "specific-comp-2"],
  "timeout_minutes": 10,
  "retry_attempts": 3
}
```

## 🚧 Casos de Uso

### 1. Nuevo Business Creado
```bash
# Procesar todos los competidores de un business recién creado
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "new-business-id",
  "process_all_competitors": true
}'
```

### 2. Actualización Periódica
```bash
# Solo procesar competidores que necesitan actualización
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "existing-business-id",
  "process_all_competitors": false
}'
```

### 3. Procesamiento Selectivo
```bash
# Procesar competidores específicos
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "business-id",
  "competitor_ids": ["comp-1", "comp-2"]
}'
```

### 4. Integración con Frontend
```javascript
// Llamada desde aplicación frontend
const response = await fetch('/api/trigger-social-media-extraction', {
  method: 'POST',
  body: JSON.stringify({
    business_id: currentBusinessId,
    process_all_competitors: true
  })
});
```

## 📚 Enlaces Útiles

- 📖 [Documentación Kestra](https://kestra.io/docs)
- 🎯 [Kestra Blueprints](https://kestra.io/blueprints)
- 📊 [Dashboard Kestra](http://localhost:8080)
- 🔗 [Instagram Analysis Pipeline](./README_INSTAGRAM_ANALYSIS_PIPELINE.md)
- 📋 [TaskIQ Documentation](https://taskiq-python.github.io/)

## ⚠️ Consideraciones Importantes

1. **Business ID Validation**: Siempre validar que el business_id existe
2. **Resource Usage**: El procesamiento puede ser intensivo en recursos
3. **Rate Limiting**: Considerar límites de scraping por sitio web
4. **Error Handling**: Manejar fallos individuales sin afectar el pipeline completo
5. **Monitoring**: Monitorear métricas de éxito por business y competidor
6. **Data Privacy**: Considerar implicaciones de privacidad al scraper sitios web 