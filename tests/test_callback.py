import requests
import json
import uuid
import datetime
import argparse

def simulate_callback(ngrok_url, request_id=None):
    """
    Simula una llamada de callback de n8n a nuestra API
    
    Args:
        ngrok_url: La URL base de ngrok (sin /api/v1/...)
        request_id: ID de la solicitud (opcional, se genera uno si no se proporciona)
    """
    if not request_id:
        request_id = str(uuid.uuid4())
    
    # Construir la URL del callback
    callback_url = f"{ngrok_url}/api/v1/analyze-competitors/callback"
    
    # Crear datos simulados de competidores
    mock_competitors = [
        {
            "name": "Competidor Test 1",
            "website": "https://competidor1.com",
            "description": "Esta es una empresa de prueba para simular callbacks",
            "strengths": ["Buena presencia online", "Precios competitivos"],
            "weaknesses": ["Servicio al cliente deficiente", "Poca variedad de productos"],
            "market_share": 15.5,
            "target_audience": "Profesionales 25-45 años",
            "pricing_strategy": "Premium",
            "unique_selling_proposition": "Calidad superior garantizada"
        },
        {
            "name": "Competidor Test 2",
            "website": "https://competidor2.com",
            "description": "Otra empresa de prueba para el callback",
            "strengths": ["Innovación constante", "Marca reconocida"],
            "weaknesses": ["Precios altos", "Tiempos de entrega largos"],
            "market_share": 8.3,
            "target_audience": "Adultos jóvenes urbanos",
            "pricing_strategy": "Value-based",
            "unique_selling_proposition": "Tecnología de punta accesible"
        }
    ]
    
    # Datos para el callback
    callback_data = {
        "request_id": request_id,
        "status": "completed",
        "competitors": mock_competitors,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    print(f"Enviando datos de callback a: {callback_url}")
    print(f"Request ID: {request_id}")
    
    try:
        # Enviar el callback
        response = requests.post(
            callback_url,
            json=callback_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verificar respuesta
        print(f"Respuesta: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        return response.json()
    
    except Exception as e:
        print(f"Error enviando callback: {str(e)}")
        return None

def simulate_error_callback(ngrok_url, request_id=None):
    """
    Simula una llamada de callback de error de n8n a nuestra API
    
    Args:
        ngrok_url: La URL base de ngrok (sin /api/v1/...)
        request_id: ID de la solicitud (opcional, se genera uno si no se proporciona)
    """
    if not request_id:
        request_id = str(uuid.uuid4())
    
    # Construir la URL del callback
    callback_url = f"{ngrok_url}/api/v1/analyze-competitors/callback"
    
    # Datos para el callback de error
    callback_data = {
        "request_id": request_id,
        "status": "error",
        "error_message": "Error simulado en la investigación de competidores. El LLM no pudo completar el análisis.",
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    print(f"Enviando datos de callback de ERROR a: {callback_url}")
    print(f"Request ID: {request_id}")
    
    try:
        # Enviar el callback
        response = requests.post(
            callback_url,
            json=callback_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verificar respuesta
        print(f"Respuesta: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        return response.json()
    
    except Exception as e:
        print(f"Error enviando callback: {str(e)}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simular callbacks de n8n")
    parser.add_argument("ngrok_url", help="URL base de ngrok (ej: https://abcd1234.ngrok.io)")
    parser.add_argument("--request-id", help="ID de solicitud específico (opcional)")
    parser.add_argument("--error", action="store_true", help="Simular un callback de error")
    
    args = parser.parse_args()
    
    if args.error:
        simulate_error_callback(args.ngrok_url, args.request_id)
    else:
        simulate_callback(args.ngrok_url, args.request_id) 