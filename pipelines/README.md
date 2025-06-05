# 🚀 Kestra Pipelines - Competitor Analysis Automation

Este directorio contiene los pipelines de Kestra para automatizar el análisis de competidores usando FastAPI + TaskIQ.

## 📋 Pipelines Disponibles

### 1. 📱 Social Media Extraction Pipeline
**File**: `social-media-extraction-trigger.yml`

Extrae información de redes sociales de los sitios web de competidores para un business específico.

**Trigger**: Webhook con `business_id`
**Endpoint**: `/api/v1/business/competitive-analysis/social-media/{business_id}`

### 2. 📸 Instagram Analysis Complete Pipeline  
**File**: `instagram-analysis-complete-trigger.yml`

Ejecuta análisis completo de Instagram en 4 pasos secuenciales después de la extracción de redes sociales.

**Trigger**: Webhook automático + Schedule + Manual
**Endpoints**: 4 endpoints de análisis de Instagram

## 🔄 Flujo Integrado

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Call      │    │   Social Media  │    │   Instagram     │
│   with          │───▶│   Extraction    │───▶│   Analysis      │
│   business_id   │    │   Pipeline      │    │   Pipeline      │
│                 │    │                 │    │                 │
│ Webhook/Manual  │    │ Find & Process  │    │ 4-Step Analysis │
│ Trigger         │    │ Competitors     │    │ (Auto-triggered)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Setup Both Pipelines

```bash
# Ejecutar script de setup automático
chmod +x pipelines/setup_complete_pipelines.sh
./pipelines/setup_complete_pipelines.sh
```

### 2. Trigger Social Media Extraction

**Para un business específico (Caso principal):**

```bash
curl -X POST http://localhost:8080/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/social_media_extraction_by_business \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": "12345678-1234-1234-1234-123456789012",
    "process_all_competitors": true,
    "max_concurrent_extractions": 3
  }'
```

### 3. Monitor Progress

- **Kestra Dashboard**: http://localhost:8080
- **Flow**: `noit.backend/social-media-extraction-trigger`
- **Instagram Flow**: `noit.backend/instagram-analysis-complete-trigger`

## 📊 Casos de Uso

### Nuevo Business Creado
```bash
# Procesar todos los competidores de un business recién creado
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "new-business-id",
  "process_all_competitors": true
}'
```

### Actualización Selectiva
```bash
# Solo procesar competidores que necesitan actualización
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "existing-business-id", 
  "process_all_competitors": false
}'
```

### Competidores Específicos
```bash
# Procesar solo ciertos competidores
curl -X POST .../social_media_extraction_by_business -d '{
  "business_id": "business-id",
  "competitor_ids": ["comp-1", "comp-2"]
}'
```

## 🎯 Parámetros Principales

### Social Media Pipeline

| Parámetro | Tipo | Required | Default | Descripción |
|-----------|------|----------|---------|-------------|
| `business_id` | STRING | ✅ Sí | - | ID del business a procesar |
| `process_all_competitors` | BOOLEAN | ❌ No | true | Procesar todos o solo los que necesitan extracción |
| `competitor_ids` | ARRAY | ❌ No | null | IDs específicos de competidores |
| `max_concurrent_extractions` | INT | ❌ No | 3 | Máximo extracciones concurrentes |

### Instagram Analysis Pipeline

| Parámetro | Tipo | Required | Default | Descripción |
|-----------|------|----------|---------|-------------|
| `business_id` | STRING | ❌ No | auto | Business ID específico |
| `triggered_by` | STRING | ❌ No | auto | Fuente que disparó el análisis |
| `max_concurrent_analysis` | INT | ❌ No | 2 | Máximo análisis concurrentes |
| `wait_timeout_minutes` | INT | ❌ No | 30 | Timeout por paso de análisis |

## 📈 Monitoreo

### Dashboard URLs
- **Kestra**: http://localhost:8080
- **Flows**: http://localhost:8080/ui/flows
- **Executions**: http://localhost:8080/ui/executions  
- **TaskIQ**: http://localhost:3000/tasks

### Health Checks
```bash
# Verificar Kestra
curl http://localhost:8080/health

# Verificar FastAPI
curl http://localhost:8000/health

# Verificar Pipelines
curl http://localhost:8080/api/v1/flows/noit.backend/social-media-extraction-trigger
```

## 🛠️ Troubleshooting

### Pipeline falla inmediatamente
1. **Verificar business_id existe**:
   ```sql
   SELECT * FROM business_ideas WHERE id = 'business-id';
   ```

2. **Verificar formato UUID**: Debe ser UUID válido

### No encuentra competidores
1. **Verificar competidores para business**:
   ```sql
   SELECT * FROM competitors 
   WHERE business_idea_id = 'business-id' 
   AND website IS NOT NULL;
   ```

### Endpoint falla
1. **Verificar FastAPI**: `curl http://localhost:8000/health`
2. **Verificar TaskIQ**: `docker logs noit_backend-taskiq-worker-1`

## 📚 Documentación Detallada

- 📖 **[Social Media Pipeline](./README_SOCIAL_MEDIA_PIPELINE.md)**: Guía completa del pipeline de extracción de redes sociales
- 📖 **[Instagram Analysis Pipeline](./README_INSTAGRAM_ANALYSIS_PIPELINE.md)**: Guía del pipeline de análisis completo de Instagram
- 🔧 **[Setup Script](./setup_complete_pipelines.sh)**: Script de instalación automática

## ⚙️ Arquitectura del Sistema

### Componentes
- **Kestra**: Orquestación y scheduling de workflows
- **FastAPI**: Endpoints REST para iniciar procesos
- **TaskIQ**: Procesamiento asíncrono distribuido
- **PostgreSQL**: Base de datos principal
- **Redis**: Cola de tareas y cache
- **MinIO**: Almacenamiento de archivos de análisis

### Flujo de Datos
1. **Webhook/API** → Kestra Pipeline
2. **Kestra** → Validación de business + Query de competidores
3. **Kestra** → HTTP Request a FastAPI endpoint
4. **FastAPI** → Queuing task en TaskIQ
5. **TaskIQ Worker** → Procesamiento (scraping, analysis)
6. **TaskIQ** → Almacenamiento en PostgreSQL + MinIO
7. **Kestra** → Auto-trigger de Instagram analysis
8. **Repetir** para análisis de Instagram

## 🚧 Próximos Pasos

1. **Rate Limiting**: Implementar límites por sitio web
2. **Batch Processing**: Optimización para múltiples businesses
3. **Error Recovery**: Retry inteligente por tipo de error
4. **Notifications**: Alertas en Slack/email
5. **Cost Control**: Límites de uso de OpenAI API
6. **Performance Monitoring**: Métricas detalladas de tiempo/costo

## ⚠️ Consideraciones

1. **Business ID Validation**: Siempre validar existencia del business
2. **Resource Management**: Monitorear uso de CPU/memoria
3. **Rate Limits**: Instagram y OpenAI tienen límites de requests  
4. **Data Privacy**: Considerar implicaciones del web scraping
5. **Cost Control**: El análisis de imágenes puede ser costoso
6. **Error Handling**: Manejar fallos sin afectar pipeline completo 