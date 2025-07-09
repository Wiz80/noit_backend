# Instagram URL Correction for Competitors

Esta funcionalidad permite encontrar y corregir automáticamente URLs de Instagram de los competidores usando OpenAI con Langchain, basándose en el nombre del competidor y su website.

## 🎯 Objetivo

Resolver el problema de URLs de Instagram faltantes o incorrectas en la base de datos de competidores, utilizando la inteligencia del LLM para inferir las cuentas correctas basándose en el nombre de la empresa y su sitio web.

## 🚀 Funcionalidades

### 1. Endpoint de Corrección de URLs de Instagram

**URL:** `POST /api/v1/analyze-competitors/instagram/{business_id}/correct-instagram-urls`

**Descripción:** Encuentra y corrige todas las URLs de Instagram de los competidores de una idea de negocio usando el conocimiento del LLM.

**Parámetros:**
```json
{
  "competitor_ids": ["uuid1", "uuid2"],  // Opcional: IDs específicos a procesar
  "force_update": false                   // Opcional: forzar actualización de URLs existentes
}
```

**Respuesta:**
```json
{
  "business_id": "uuid",
  "total_competitors": 5,
  "corrected_count": 3,
  "skipped_count": 2,
  "corrected_instagram_urls": [
    {
      "competitor_id": "uuid",
      "competitor_name": "Nike",
      "competitor_website": "https://nike.com",
      "original_instagram_url": null,
      "corrected_instagram_url": "https://instagram.com/nike",
      "was_corrected": true,
      "confidence_score": 0.95,
      "reasoning": "Well-known brand with verified Instagram account matching company name"
    }
  ],
  "success": true,
  "message": "Successfully found/corrected 3 Instagram URLs for all competitors for this business"
}
```

## 🔧 Cómo Funciona

### 1. Análisis de Competidores

El sistema analiza automáticamente:
- **Nombre del competidor:** Para identificar patrones de naming
- **Website:** Para extraer dominios y nombres de marca
- **URLs existentes:** Para determinar si necesita actualización

### 2. Inteligencia del LLM

El LLM utiliza:
- **Conocimiento de marcas conocidas:** Para empresas famosas
- **Patrones de naming:** Para inferir handles probables
- **Análisis de dominios:** Para convertir website.com → @website
- **Verificación de confianza:** Score de 0.0-1.0 basado en certeza

### 3. Criterios de Detección

El LLM busca:
- Cuentas verificadas de empresas conocidas
- Handles que coincidan con el nombre de la empresa
- Usernames derivados del dominio del website
- Patrones comunes de redes sociales empresariales

### 4. Validación y Actualización

- Solo actualiza URLs con alta confianza
- Proporciona razonamiento para cada decisión
- Mantiene URLs originales si no encuentra mejores opciones
- Transacción atómica para garantizar consistencia

## 📋 Casos de Uso

### 1. Empresas Conocidas
```json
{
  "competitor_name": "Nike",
  "website": "https://nike.com",
  "result": "https://instagram.com/nike",
  "confidence": 0.95,
  "reasoning": "Well-known brand with verified Instagram account"
}
```

### 2. Empresas Locales
```json
{
  "competitor_name": "Café Central",
  "website": "https://cafecentral.com.co",
  "result": "https://instagram.com/cafecentral",
  "confidence": 0.75,
  "reasoning": "Website domain matches likely Instagram handle pattern"
}
```

### 3. Casos Inciertos
```json
{
  "competitor_name": "Tech Solutions Inc",
  "website": "https://techsol.com",
  "result": null,
  "confidence": 0.3,
  "reasoning": "Multiple possible variations exist, cannot confidently determine correct account"
}
```

## 🔍 Tipos de Resultados

### ✅ **Alta Confianza (0.8-1.0)**
- Marcas conocidas con cuentas verificadas
- Coincidencias exactas de nombre/dominio
- Patrones empresariales claros

### ⚠️ **Confianza Media (0.5-0.7)**
- Patrones probables pero no confirmados
- Empresas menos conocidas con handles lógicos
- Derivaciones de dominio razonables

### ❌ **Baja Confianza (0.0-0.4)**
- Múltiples posibilidades ambiguas
- Nombres muy genéricos
- Sin presencia clara en Instagram

## 📊 Ejemplo de Uso Completo

```bash
# 1. Encontrar URLs de Instagram para todos los competidores
curl -X POST "http://localhost:8000/api/v1/analyze-competitors/instagram/{business_id}/correct-instagram-urls" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "force_update": false
  }'

# 2. Forzar actualización de competidores específicos
curl -X POST "http://localhost:8000/api/v1/analyze-competitors/instagram/{business_id}/correct-instagram-urls" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "competitor_ids": ["uuid1", "uuid2"],
    "force_update": true
  }'
```

## 🚨 Consideraciones

### **Limitaciones del LLM**
- Basado en conocimiento de entrenamiento (no busca en tiempo real)
- Puede no conocer empresas muy nuevas o locales
- No verifica si las cuentas están activas actualmente

### **Filtros de Calidad**
- Solo URLs con confidence_score > 0.5 se consideran válidas
- URLs null se asignan cuando la confianza es muy baja
- Razonamiento detallado para cada decisión

### **Casos Especiales**
- Empresas con múltiples cuentas regionales
- Cambios de branding recientes
- Cuentas personales vs empresariales

## 🔒 Seguridad

- **Autenticación:** Requiere usuario superadmin
- **Validación:** Verificación de business_id y competitor_ids
- **Logs de auditoría:** Todas las correcciones se registran
- **Rate limiting:** Controlado por configuración de OpenAI

## ⚙️ Configuración

Asegúrate de tener configuradas las siguientes variables de entorno:
```bash
OPENAI_API_KEY=your-openai-api-key
```

## 📈 Métricas de Rendimiento

El endpoint proporciona métricas detalladas:
- Total de competidores procesados
- Número de URLs encontradas/corregidas
- Número de competidores omitidos
- Distribución de scores de confianza
- Tiempo de procesamiento

## 🔄 Flujo de Trabajo Recomendado

1. **Primera ejecución:** Procesar todos los competidores para poblar URLs faltantes
2. **Actualizaciones periódicas:** Usar `force_update: false` para nuevos competidores
3. **Correcciones manuales:** Revisar URLs con baja confianza
4. **Validación manual:** Verificar URLs de alta prioridad antes de usar para scraping 