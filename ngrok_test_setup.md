# CONFIGURACIÓN DE PRUEBA CON NGROK

Este documento describe cómo configurar ngrok para exponer temporalmente la API local a internet y recibir callbacks de n8n.

## Requisitos

1. [ngrok](https://ngrok.com/) instalado localmente
2. API FastAPI ejecutándose localmente (por ejemplo en el puerto 8000)
3. Acceso al workflow de n8n

## Pasos para Configurar

### 1. Ejecutar la API FastAPI

Asegúrate de que tu API está ejecutándose localmente:

```bash
# Desde el directorio raíz del proyecto
uvicorn app.main:app --reload --port 8000
```

### 2. Iniciar ngrok para exponer el puerto

En una nueva terminal, ejecuta:

```bash
ngrok http 8000
```

ngrok generará una URL pública temporal (por ejemplo: `https://abcd1234.ngrok.io`) que redirige al puerto 8000 de tu máquina local.

### 3. Configurar la URL de Callback

Cuando hagas una solicitud a la API para iniciar la investigación de competidores, usa la URL de ngrok como base:

```json
{
  "search_prompt": "Analiza los competidores para mi negocio",
  "language": "es",
  "validator_provider": "openai",
  "validator_model": "gpt-4",
  "research_model": "claude-3-haiku",
  "base_url": "https://abcd1234.ngrok.io"  // URL proporcionada por ngrok
}
```

La API construirá la URL de callback completa utilizando esta base:
`https://abcd1234.ngrok.io/api/v1/analyze-competitors/callback`

### 4. Configurar el Workflow de n8n

En tu workflow de n8n:

1. Abre el nodo "Set" para procesar variables
2. Verifica que estás extrayendo correctamente `callback_url`, `request_id` y `business_id`
3. Configura el nodo HTTP Request para hacer POST a la URL de callback

#### Configuración Correcta del Nodo HTTP Request:

- Method: POST
- URL: `={{$node["Set"].json.callback_url}}`
- Headers:
  - Content-Type: application/json
- Body (JSON):
```json
{
  "request_id": "={{$node['Set'].json.request_id}}",
  "status": "completed",
  "competitors": {{$json.results}},
  "timestamp": "{{$now.toISOString()}}"
}
```

> ⚠️ **IMPORTANTE**: Si tu nodo genera un resultado en formato texto en lugar de JSON, usa:
```json
{
  "request_id": "={{$node['Set'].json.request_id}}",
  "status": "completed", 
  "competitors": "={{$json.results}}",
  "timestamp": "{{$now.toISOString()}}"
}
```

### 5. Prueba del Flujo Completo

1. Inicia el ngrok y copia la URL generada
2. Envía una solicitud a tu API usando esa URL como `base_url`
3. Verifica en la consola de FastAPI que la solicitud inicial se procesa correctamente
4. Una vez que n8n termine la investigación, debería hacer la llamada de callback
5. Verifica que FastAPI recibe el callback y procesa los resultados correctamente

### Monitoreo y Depuración

- En el panel web de ngrok (http://localhost:4040) puedes ver todo el tráfico HTTP
- Revisa los logs de FastAPI para confirmar que recibe tanto la solicitud inicial como el callback
- Verifica en n8n que los datos se están procesando correctamente

## Solución de Problemas Comunes

### Error 422 (Unprocessable Entity)

Si recibes un error 422 al hacer el callback:

1. Verifica el payload enviado en el panel de ngrok
2. Asegúrate de que estás enviando **exactamente** estos campos obligatorios:
   - `request_id` (el mismo que recibiste en la solicitud inicial)  
   - `status` (debe ser "completed" o "error")

3. Si el payload contiene otros campos que no coinciden con el esquema, elimínalos
4. Verifica que las referencias {{}} en n8n sean correctas:
   - Usar comillas para valores string: `"competitors": "={{$json.results}}"`
   - Omitir comillas para objetos JSON: `"competitors": {{$json.results}}`

### Error de "Read timeout"

Si ves errores de timeout:

1. Aumenta el timeout en el nodo HTTP Request de n8n (a 120 segundos o más)
2. Verifica que ngrok sigue funcionando y la API está respondiendo
3. Considera si los resultados son muy grandes; en tal caso, implementa una solución de streaming

### Consideraciones

- Las URLs de ngrok expiran después de un tiempo (dependiendo de tu plan)
- Para pruebas prolongadas, considera usar un servicio como [serveo.net](https://serveo.net/) o [pagekite.net](https://pagekite.net/)
- En producción, debes tener una URL pública permanente para tu API
