# Pruebas del Sistema de Investigación de Competidores con n8n y Callbacks

Este documento explica cómo probar el sistema completo de investigación de competidores usando ngrok como intermediario para los callbacks.

## Requisitos

- Python 3.7+ con las bibliotecas `requests` y `argparse`
- [ngrok](https://ngrok.com/) instalado
- Acceso al workflow de n8n
- API FastAPI en ejecución local

## Orden de Ejecución

### 1. Configurar el Entorno

1. Iniciar la API FastAPI local:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. En otra terminal, iniciar ngrok para exponer el puerto 8000:
   ```bash
   ngrok http 8000
   ```
   
3. Tomar nota de la URL de ngrok generada (ej: `https://abcd1234.ngrok.io`)

4. Configurar el workflow n8n para recibir solicitudes y enviar callbacks (consulta `n8n_callback_guide.md` para detalles)

### 2. Pruebas Manuales

#### Iniciar una Investigación

Ejecuta el script `test_start_research.py` para iniciar una investigación:

```bash
python test_start_research.py https://abcd1234.ngrok.io business-id-123
```

Donde:
- `https://abcd1234.ngrok.io` es la URL generada por ngrok
- `business-id-123` es el ID del negocio para el que quieres analizar competidores

Si quieres personalizar el prompt de búsqueda:

```bash
python test_start_research.py https://abcd1234.ngrok.io business-id-123 --prompt "Busca competidores en España para una app de delivery de comida"
```

#### Verificar Estado de la Investigación

Tras iniciar una investigación, puedes consultar su estado:

```bash
python check_status.py https://abcd1234.ngrok.io request-id-456
```

Para consultar continuamente hasta que se complete:

```bash
python check_status.py https://abcd1234.ngrok.io request-id-456 --poll
```

#### Simular Callbacks de n8n

Si quieres probar el endpoint de callback sin esperar a que n8n termine:

```bash
python test_callback.py https://abcd1234.ngrok.io --request-id request-id-456
```

Para simular un error:

```bash
python test_callback.py https://abcd1234.ngrok.io --request-id request-id-456 --error
```

### 3. Verificación del Flujo Completo

1. **Iniciar investigación**: Usa `test_start_research.py` para enviar la solicitud inicial
2. **Verificar recepción en n8n**: Confirma que n8n recibe la solicitud con el URL de callback
3. **Verificar estado**: Usa `check_status.py` para monitorear el progreso
4. **Esperar callback**: Cuando n8n termine, enviará los resultados al callback URL
5. **Verificar resultados finales**: Vuelve a usar `check_status.py` para ver los resultados completos

## Monitorización

- **Panel de ngrok**: Visita http://localhost:4040 para ver todo el tráfico HTTP que pasa por ngrok
- **Logs de FastAPI**: Revisa la terminal donde se ejecuta FastAPI para ver logs de solicitudes y callbacks
- **Panel de n8n**: Verifica la ejecución del workflow y cualquier error

## Solución de Problemas

- **Callback no llega**: Verifica que la URL de ngrok sea accesible y que n8n tenga permiso para hacer solicitudes HTTP externas
- **Error 404**: Verifica que las rutas de la API estén correctamente configuradas
- **Error en n8n**: Revisa los logs de n8n para entender qué está fallando en el procesamiento

## Transición a Producción

Una vez que hayas verificado que todo funciona correctamente con ngrok:

1. Reemplaza la URL de ngrok con tu URL de producción
2. Actualiza la configuración del workflow de n8n para usar la URL de producción
3. Implementa el manejo de errores y reintentos adecuados para entornos de producción 