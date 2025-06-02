# CrewAI Brief Agent Testing

Este directorio contiene tests completos para el **BriefAgentService** que usa CrewAI para gestionar conversaciones inteligentes de brief de negocio.

## Tipos de Tests

### 1. Test Completo de Performance (`test_brief_agent_crewai_flow.py`)

Un test exhaustivo que evalúa el rendimiento del BriefAgentService siguiendo los patrones de testing de CrewAI.

**Características:**
- ✅ **Multi-escenario**: Testa 3 tipos de negocio diferentes (Tech Startup, E-commerce, Servicios)
- ✅ **Múltiples iteraciones**: Ejecuta cada escenario 2 veces por defecto
- ✅ **Métricas detalladas**: Evalúa 5 aspectos clave del flujo de conversación
- ✅ **Reporte estilo CrewAI**: Genera reportes similares al comando `crewai test`

**Métricas evaluadas:**
1. **Welcome Flow**: Calidad del mensaje de bienvenida y primera pregunta
2. **Question Progression**: Fluidez en la progresión de preguntas
3. **Response Validation**: Capacidad de validar respuestas del usuario
4. **Suggestion Quality**: Calidad de las sugerencias contextuales
5. **Completion Handling**: Manejo del completado del brief

### 2. Test Simple Compatible (`test_brief_crewai_simple.py`)

Un test simple que puede ser usado con el comando `crewai test` directamente.

## Cómo Ejecutar los Tests

### Test Completo

```bash
# Ejecutar el test completo de performance
cd /Users/soul/Documents/infinity_lab/noit_backend
poetry run python tests/services/test_brief_agent_crewai_flow.py
```

### Test Simple con CrewAI CLI

```bash
# Usar el comando oficial de CrewAI (si está configurado)
crewai test -n 3 -m gpt-4o-mini
```

### Test Manual Básico

```bash
# Ejecutar el test básico existente
poetry run python tests/services/test_brief_agent.py
```

## Formato de Resultados

Los tests generan resultados en formato similar a CrewAI:

```
📊 CREWAI BRIEF AGENT FLOW - TEST RESULTS
================================================================================
🔍 Total Scenarios: 3
🔄 Iterations per scenario: 2
⚡ Total test iterations: 6
📈 Overall Average Score: 8.5/10
⏱️  Overall Average Time: 12.3s

📋 SCENARIO BREAKDOWN
--------------------------------------------------------------------------------
Scenario                  Run 1    Run 2    Avg Score  Avg Time   Status    
--------------------------------------------------------------------------------
Tech Startup Scenario     8.8      8.6      8.7        11.2s      ✅ Excellent
E-commerce Scenario        8.4      8.2      8.3        13.1s      ✅ Excellent  
Service Business Scenario 8.6      8.4      8.5        12.6s      ✅ Excellent
--------------------------------------------------------------------------------

🏆 OVERALL ASSESSMENT: 🎉 EXCELLENT - CrewAI Brief Flow is performing exceptionally well!
```

## Configuración de Environment

Asegúrate de tener las variables de entorno necesarias:

```bash
export OPENAI_API_KEY="your-openai-key"
# O cualquier otro proveedor de LLM que uses
```

## Estructura de Test

### Escenarios de Prueba

Cada escenario incluye:
- **Datos del negocio**: Información contextual para las sugerencias
- **Respuestas de muestra**: Respuestas típicas que un usuario podría dar
- **Evaluación multi-dimensional**: Scoring en 5 áreas clave

### Criterios de Evaluación

**Scoring (0-10 por métrica):**
- **8-10**: Excellent ✅
- **6-8**: Good ✅  
- **4-6**: Fair ⚠️
- **0-4**: Poor ❌

### Archivos de Resultado

Los tests generan archivos JSON con resultados detallados:
- `crewai_brief_test_results_YYYYMMDD_HHMMSS.json`

## Troubleshooting

### Errores Comunes

1. **Importation errors**: Verifica que estés en el directorio root del proyecto
2. **API Key missing**: Asegúrate de tener las variables de entorno configuradas
3. **CrewAI timeout**: Ajusta el timeout si tienes conexión lenta

### Debug Mode

Para ejecutar con más logging:

```bash
PYTHONPATH=. poetry run python tests/services/test_brief_agent_crewai_flow.py
```

## Mejoras Futuras

- [ ] Integración con pytest
- [ ] Tests de carga (load testing)
- [ ] Métricas de calidad de respuesta usando LLM evaluation
- [ ] Tests de recuperación de sesión desde Redis
- [ ] Tests de integración con MinIO

## Contribución

Para agregar nuevos escenarios de test:

1. Edita `_prepare_test_scenarios()` en `test_brief_agent_crewai_flow.py`
2. Agrega nuevos datos de negocio y respuestas de muestra
3. Considera agregar nuevas métricas si es necesario 