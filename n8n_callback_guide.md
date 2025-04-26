# N8N CALLBACK WORKFLOW CONFIGURATION GUIDE

Este documento explica cómo configurar un workflow de n8n para realizar investigaciones profundas y enviar los resultados de vuelta a la API a través de un callback.

## Flujo del Proceso

1. La API llama al webhook de n8n con los datos de investigación y URL de callback
2. N8n procesa la investigación (puede tomar tiempo)
3. Al finalizar, n8n envía los resultados a la URL de callback especificada
4. La API procesa los resultados y actualiza la base de datos/MinIO

## Configuración del Workflow en n8n

### 1. Webhook Trigger

1. Añade un nodo "Webhook" como trigger
2. Configúralo como "POST"
3. Guarda el webhook y copia la URL generada para configurar en la API

### 2. Procesamiento de la Solicitud (IMPORTANTE)

1. Añade un nodo de "Set" para extraer datos importantes:
   ```
   Items[0].json.search_query = $json.search_query
   Items[0].json.lang = $json.lang
   Items[0].json.model = $json.model
   Items[0].json.callback_url = $json.callback_url
   Items[0].json.request_id = $json.request_id
   Items[0].json.business_id = $json.business_id
   Items[0].json.base_url = $json.base_url
   ```
   
   > ⚠️ **MUY IMPORTANTE**: El `request_id` y `business_id` deben ser EXACTAMENTE los mismos valores que se recibieron en la solicitud original de la API. No generes nuevos valores para estos campos, ya que se usan para buscar registros en la base de datos.

### 3. Investigación

1. Añade tu flujo de research actual con LLM o herramientas específicas
2. Asegúrate que el resultado se guarde en una variable, por ejemplo `results`

### 4. Nodo de Function para Procesar el Texto (IMPORTANTE)

Para el caso específico de procesar texto y citations como en el ejemplo:

```javascript
// Script para procesar correctamente el resultado de la investigación
const cleanAndStructureResponse = (item) => {
  // IMPORTANTE: Preservar el request_id y business_id exactos de la solicitud original
  const requestId = $('Webhook').first().json.body.request_id || "";
  const businessId = $('Webhook').first().json.body.business_id || "";
  
  // Si estamos trabajando con un array de objetos (como en el ejemplo)
  if (Array.isArray(item.json)) {
    // Extraer y limpiar el texto y las citas
    const result = {};
    
    // Obtener el primer elemento que contiene text y citations
    const firstItem = item.json[0];
    
    if (firstItem && firstItem.text && firstItem.citations) {
      // Limpiar el texto eliminando caracteres problemáticos
      result.text = firstItem.text.trim();
      
      // Limpiar las citas
      result.citations = firstItem.citations.trim();
      
      // Asegurarnos de incluir los IDs originales
      result.request_id = requestId;
      result.business_id = businessId;
      
      return { json: result };
    }
  }
  
  // Si ya tenemos un objeto con text y citations
  if (item.json && item.json.text && item.json.citations) {
    const result = {
      text: item.json.text.trim(),
      citations: item.json.citations.trim(),
      request_id: requestId,
      business_id: businessId
    };
    
    return { json: result };
  }
  
  // En caso de que el formato no coincida, devolver el original y añadir los IDs
  const result = {...item.json, request_id: requestId, business_id: businessId};
  return { json: result };
};

// Procesar el item actual
return cleanAndStructureResponse($input.item);
```

### 5. Nodo de Webhook Callback (IMPORTANTE - CONFIGURACIÓN CORREGIDA)

1. Añade un nodo "HTTP Request" que se ejecutará después del nodo Function:
   - Method: POST
   - URL: `={{$node["Set"].json.callback_url}}`
   - Headers: 
     - Content-Type: application/json
   - Body: JSON
   ```json
   {
     "request_id": "={{$node['Webhook'].first().json.body.request_id}}",
     "business_id": "={{$node['Webhook'].first().json.body.business_id}}",
     "status": "completed",
     "search_prompt": "={{$node['Set'].json.search_query}}",
     "base_url": "={{$node['Set'].json.base_url}}",
     "competitors": {{$json.text}}
   }
   ```

   > ⚠️ **IMPORTANTE**: 
   > - Usa `$node['Webhook'].first().json.body.request_id` en lugar de `$node['Set'].json.request_id` para asegurar que estás usando el ID original
   > - Usa `$node['Webhook'].first().json.body.business_id` en lugar de `$node['Set'].json.business_id` por la misma razón
   > - El campo "status" es **OBLIGATORIO** y debe ser "completed" o "error"
   > - El campo "search_prompt" es **OBLIGATORIO** según el error 422
   > - El campo "base_url" es **OBLIGATORIO** según el último error 422
   > - Los campos request_id y business_id son fundamentales y deben ser los originales

### 6. Manejo de Errores

1. Añade un nodo "Error Trigger" para capturar cualquier error
2. Conecta a un nodo HTTP Request para notificar el error:
   - Method: POST
   - URL: `={{$node["Set"].json.callback_url}}`
   - Headers:
     - Content-Type: application/json  
   - Body: JSON
   ```json
   {
     "request_id": "={{$node['Webhook'].first().json.body.request_id}}",
     "business_id": "={{$node['Webhook'].first().json.body.business_id}}",
     "status": "error",
     "search_prompt": "={{$node['Set'].json.search_query}}",
     "base_url": "={{$node['Set'].json.base_url}}",
     "error_message": "={{$error.message}}"
   }
   ```

### 7. Nodo de Respuesta

1. Añade un nodo "Respond to Webhook" para dar respuesta inmediata a la API
2. Configura con:
   ```json
   {
     "status": "accepted",
     "message": "Research started successfully",
     "request_id": "={{$node['Webhook'].first().json.body.request_id}}"
   }
   ```

## Ejemplo Visual del Workflow

```
[Webhook Trigger] → [Set Variables] → [Respond to Webhook] → [Research Process] → [Function (Limpiar Texto)] → [HTTP Callback]
                                     ↓                                                                           ↑
                                     [Error Trigger] → [Error HTTP Callback] →→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→→
```

## Solución al Error "Business idea not found"

Si estás recibiendo el error "Business idea not found", significa que el sistema no puede encontrar un registro de negocio válido asociado con el callback. Esto puede suceder por varias razones:

1. **El request_id no coincide**: El `request_id` que estás enviando en el callback debe ser EXACTAMENTE el mismo que recibiste en la solicitud inicial. Verifica que estás usando el `request_id` original y no generando uno nuevo.

2. **El business_id no coincide**: El `business_id` debe corresponder a un registro válido en la base de datos. Asegúrate de que estás enviando el `business_id` original.

3. **Acceso a los valores originales**: Usa `$node['Webhook'].first().json.body.request_id` y `$node['Webhook'].first().json.body.business_id` para acceder a los valores originales en lugar de los valores intermedios.

Para verificar los valores que estás recibiendo, añade un nodo "Debug" justo después del Webhook y verifica que los valores de request_id y business_id sean correctos.

## Solución al Error "Field required | Field required"

Si estás recibiendo el error "Field required", asegúrate de que tu payload contiene TODOS los campos obligatorios:

```json
{
  "request_id": "{{ $('Webhook').first().json.body.request_id }}",
  "business_id": "{{ $('Webhook').first().json.body.business_id }}",
  "status": "completed",  <!-- CAMPO OBLIGATORIO -->
  "search_prompt": "{{ $('Webhook').first().json.body.search_query }}", <!-- CAMPO OBLIGATORIO -->
  "base_url": "{{ $('Webhook').first().json.body.base_url }}", <!-- CAMPO OBLIGATORIO -->
  "competitors": "{{ $json.text }}"
}
```

Ten en cuenta que el campo `status` es obligatorio y debe tener uno de los siguientes valores:
- "completed": si la investigación se completó correctamente
- "error": si hubo un error durante la investigación

Según el error 422, los campos `search_prompt` y `base_url` también son obligatorios y deben ser proporcionados para que la API procese correctamente el callback.

## JavaScript para Formato Específico con Text y Citations

Para el caso específico mostrado en el ejemplo donde tienes un array con un objeto que contiene `text` y `citations`, usa esta función mejorada en el nodo Function:

```javascript
// Función optimizada para el formato específico con text y citations
let result = {};

// IMPORTANTE: Obtener los valores ORIGINALES del webhook
const webhookBody = $('Webhook').first().json.body;
const businessId = webhookBody.business_id;
const requestId = webhookBody.request_id;
const searchQuery = webhookBody.search_query;
const baseUrl = webhookBody.base_url;

// Verificar que tenemos los valores originales
if (!requestId || !businessId) {
  // Log de error si faltan valores críticos
  console.log('ERROR: Faltan request_id o business_id originales del webhook');
}

// Si tenemos un array con el formato [{ text: "...", citations: "..." }]
if (Array.isArray($json) && $json.length > 0 && $json[0].text) {
  const item = $json[0];
  
  // Extraer y limpiar el texto
  if (item.text) {
    const textContent = item.text.trim();
    
    // Eliminar cualquier caracter especial que pueda causar problemas
    result.text = textContent
      .replace(/\u0000/g, '')  // Eliminar caracteres nulos
      .replace(/[\r\n]+/g, '\n') // Normalizar saltos de línea
      .replace(/\\/g, '\\\\'); // Escapar barras invertidas
  }
  
  // Extraer y limpiar las citas
  if (item.citations) {
    result.citations = item.citations
      .trim()
      .replace(/\u0000/g, '')
      .replace(/[\r\n]+/g, '\n')
      .replace(/\\/g, '\\\\');
  }
}
// Si ya tenemos un objeto con el formato correcto
else if ($json.text) {
  result = {
    text: $json.text.trim()
      .replace(/\u0000/g, '')
      .replace(/[\r\n]+/g, '\n')
      .replace(/\\/g, '\\\\'),
    citations: $json.citations ? 
      $json.citations.trim()
        .replace(/\u0000/g, '')
        .replace(/[\r\n]+/g, '\n')
        .replace(/\\/g, '\\\\')
      : ""
  };
}
// Si no tiene el formato esperado, usar el valor original
else {
  result = $json;
}

// IMPORTANTE: Usar los valores ORIGINALES del webhook
result.request_id = requestId;
result.business_id = businessId;
result.search_query = searchQuery;
result.base_url = baseUrl;

return { json: result };
```

## Troubleshooting Errores Comunes

### Error 422 (Unprocessable Entity)

Si recibes un error 422, verifica:

1. Que estás enviando al menos los campos obligatorios (`request_id`, `business_id`, `status`, `search_prompt`, `base_url`)
2. Que el formato de tus datos sea correcto (JSON válido)
3. Que no estés enviando campos adicionales que causan problemas (como el timestamp)

### Error 404 (Not Found - Business idea not found)

Si recibes un error 404 con el mensaje "Business idea not found":

1. Verifica que estás usando el `request_id` y `business_id` ORIGINALES que recibiste en la llamada al webhook
2. Comprueba que el `business_id` corresponde a un negocio existente en la base de datos
3. Asegúrate de que el registro de investigación asociado con el `request_id` aún existe y no ha caducado

### Verificación Final

Para verificar el formato antes de enviar al webhook:

1. Añade un nodo "Debug" después del nodo Webhook para ver los valores originales
2. Añade otro nodo "Debug" después del nodo Function para inspeccionar la estructura de datos final
3. Verifica que los valores de request_id y business_id son los mismos en ambos nodos Debug

## Verificación

Para verificar que el proceso funcione:

1. Envía una solicitud a la API con un endpoint de callback (puedes usar RequestBin para pruebas)
2. Verifica que la API recibe la respuesta inmediata "accepted"
3. Una vez completada la investigación, confirma que el n8n envía los resultados al callback
4. Verifica que la API procesa correctamente el callback

## Consideraciones de Timeout

- Configura tiempos de espera adecuados para investigaciones largas
- Considera usar un nodo "Set" para limitar el tiempo de procesamiento
- Para investigaciones muy largas, considera dividir el proceso en múltiples workflows
