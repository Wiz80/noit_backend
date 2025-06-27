# Competitor Pricing Scraper Testing

Este directorio contiene scripts de testing para el módulo de scraping de precios de competidores (`CompetitorPricingScraper`).

## Archivos de Testing

### 1. `test_competitor_pricing_scraper.py`
Test suite completo usando pytest para testing automatizado del módulo.

**Características:**
- Tests unitarios para cada función del scraper
- Tests de integración con las URLs proporcionadas
- Validación de parsing de precios
- Tests de normalización de URLs
- Tests de extracción por lotes

**Ejecución:**
```bash
# Ejecutar todos los tests
pytest tests/services/competitive_analysis/test_competitor_pricing_scraper.py -v

# Ejecutar un test específico
pytest tests/services/competitive_analysis/test_competitor_pricing_scraper.py::TestCompetitorPricingScraper::test_udemy_pricing_extraction -v

# Ejecutar sin pytest (modo directo)
python tests/services/competitive_analysis/test_competitor_pricing_scraper.py
```

### 2. `quick_test_competitor_pricing.py`
Script interactivo para testing rápido y debugging.

**Características:**
- Modo interactivo para probar URLs específicas
- Tests predefinidos para las URLs objetivo
- Modo de solo búsqueda de URLs
- Resultados detallados con timing
- Guardado de resultados en JSON

**Ejecución:**
```bash
python tests/services/competitive_analysis/quick_test_competitor_pricing.py
```

## URLs de Testing

El scraper se ha probado con las siguientes URLs:

1. **Udemy** - `https://www.udemy.com/`
   - Plataforma de cursos online
   - Precios en USD principalmente
   - Múltiples productos y categorías

2. **Codecademy** - `https://www.codecademy.com/`
   - Plataforma de aprendizaje de programación
   - Planes de suscripción
   - Cursos gratuitos y premium

3. **Crehana** - `https://www.crehana.com/`
   - Plataforma latinoamericana de cursos creativos
   - Precios en múltiples monedas
   - Enfoque en mercado hispanohablante

4. **SambaNova** - `https://sambanova.ai/`
   - Plataforma de AI/ML
   - Servicios empresariales
   - Pricing más complejo

5. **Platzi** - `https://platzi.com/`
   - Plataforma educativa latinoamericana
   - Precios en USD y monedas locales
   - Suscripciones y cursos individuales

## Configuración Requerida

### Variables de Entorno
Asegúrate de tener configuradas las siguientes variables en tu archivo `.env`:

```env
OPENAI_API_KEY=tu_api_key_aqui
```

### Dependencias
Las siguientes dependencias son necesarias:
- `scrapegraphai`
- `playwright`
- `openai`
- `pydantic`
- `pytest` (para tests automáticos)
- `python-dotenv`

## Tipos de Tests

### 1. Tests de Funcionalidad Básica
- Verificar que el scraper puede conectarse a las URLs
- Validar la estructura de respuesta
- Comprobar manejo de errores

### 2. Tests de Extracción de URLs
- Encontrar URLs de pricing en sitios web
- Detectar páginas de productos
- Validar normalización de URLs

### 3. Tests de Extracción de Productos
- Extraer información de productos/servicios
- Parsear precios en diferentes formatos
- Manejar monedas latinoamericanas

### 4. Tests de Parsing de Precios
- Formato colombiano: `$50.000`
- Formato internacional: `$19.99 USD`
- Rangos de precios
- Monedas múltiples

## Ejemplos de Uso

### Test Rápido de una URL
```python
from app.services.scrape.competitor_pricing_scraper import extract_competitor_pricing

result = await extract_competitor_pricing(
    website_url="https://www.codecademy.com/",
    llm_provider="openai",
    llm_model="gpt-4o-mini"
)

print(f"Products found: {result['total_products']}")
```

### Test de Solo Búsqueda de URLs
```python
scraper = CompetitorPricingScraper()
urls = await scraper.find_pricing_urls("https://www.udemy.com/")
print(f"Pricing URLs: {urls['pricing_urls']}")
```

## Interpretación de Resultados

### Estructura de Respuesta
```json
{
  "website_url": "https://example.com/",
  "pricing_urls": ["https://example.com/pricing"],
  "products_urls": ["https://example.com/products"],
  "products": [
    {
      "name": "Product Name",
      "price": "$19.99",
      "currency": "USD",
      "description": "Product description",
      "product_url": "https://example.com/product/1",
      "image_urls": ["https://example.com/image.jpg"],
      "parsed_price": 19.99,
      "source_url": "https://example.com/products"
    }
  ],
  "total_products": 1
}
```

### Métricas de Éxito
- **URLs encontradas**: Cantidad de URLs de pricing y productos detectadas
- **Productos extraídos**: Número total de productos/servicios identificados
- **Precios parseados**: Cantidad de precios exitosamente convertidos a formato numérico
- **Tiempo de ejecución**: Duración del proceso de scraping

## Troubleshooting

### Errores Comunes
1. **API Key no configurada**: Verificar `OPENAI_API_KEY` en `.env`
2. **Timeouts**: Algunos sitios pueden ser lentos, ajustar timeouts
3. **Captchas**: Algunos sitios tienen protección anti-bot
4. **Rate limiting**: Agregar delays entre requests

### Tips de Debugging
- Usar `verbose=True` en el scraper para más logs
- Probar primero con `headless=False` para ver el browser
- Verificar URLs manualmente antes de automatizar
- Usar el modo interactivo para debugging específico

## Contribución

Para agregar nuevos tests:
1. Agregar la URL a `TEST_URLS` en los scripts
2. Crear un método de test específico si es necesario
3. Documentar peculiaridades del sitio web
4. Actualizar este README

## Notas de Rendimiento

- El scraping puede tomar 30-60 segundos por sitio
- ScrapeGraphAI usa modelos LLM que consumen tokens
- Playwright puede usar recursos significativos
- Considerar usar caching para desarrollo iterativo 