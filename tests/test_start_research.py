import requests
import json
import argparse
import time

def start_competitor_research(ngrok_url, business_id, search_prompt):
    """
    Inicia una investigación de competidores usando la URL de ngrok como base
    
    Args:
        ngrok_url: URL base de ngrok (sin /api/v1/...)
        business_id: ID del negocio para el que se analizan competidores
        search_prompt: Prompt para la búsqueda de competidores
    """
    # Construir la URL del endpoint
    api_url = f"{ngrok_url}/api/v1/analyze-competitors/{business_id}"
    
    # Datos para la solicitud
    request_data = {
        "search_prompt": search_prompt,
        "language": "es",
        "validator_provider": "openai",
        "validator_model": "gpt-4",
        "research_model": "claude-3-haiku",
        "base_url": ngrok_url  # La URL de ngrok como base para callbacks
    }
    
    print(f"Iniciando investigación para negocio ID: {business_id}")
    print(f"URL: {api_url}")
    print(f"Usando URL de callback base: {ngrok_url}")
    
    try:
        # Enviar la solicitud
        response = requests.post(
            api_url,
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        # Verificar respuesta
        print(f"Respuesta: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        # Extraer el request_id para consultas posteriores
        if response.status_code == 202:
            request_id = response.json().get("request_id")
            print(f"\nLa investigación se ha iniciado con éxito.")
            print(f"Request ID: {request_id}")
            print(f"\nPuedes consultar el estado con:")
            print(f"python check_status.py {ngrok_url} {request_id}")
            
            return request_id
        else:
            print("Error iniciando la investigación")
            return None
    
    except Exception as e:
        print(f"Error enviando solicitud: {str(e)}")
        return None

def check_research_status(ngrok_url, request_id, poll=False, interval=5, max_attempts=10):
    """
    Consulta el estado de una investigación en curso
    
    Args:
        ngrok_url: URL base de ngrok
        request_id: ID de la solicitud
        poll: Si es True, consulta periódicamente hasta completar
        interval: Intervalo entre consultas en segundos
        max_attempts: Número máximo de intentos
    """
    # Construir la URL del endpoint de estado
    status_url = f"{ngrok_url}/api/v1/analyze-competitors/status/{request_id}"
    
    print(f"Consultando estado de investigación: {request_id}")
    print(f"URL: {status_url}")
    
    attempts = 0
    
    while True:
        try:
            # Enviar la solicitud
            response = requests.get(status_url)
            
            # Verificar respuesta
            data = response.json()
            status = data.get("status", "unknown")
            
            print(f"Estado actual: {status}")
            
            if not poll or status in ["completed", "error"] or attempts >= max_attempts:
                print(json.dumps(data, indent=2))
                return data
            
            # Si estamos en modo poll, esperar y reintentar
            print(f"Esperando {interval} segundos para la siguiente consulta...")
            time.sleep(interval)
            attempts += 1
            
        except Exception as e:
            print(f"Error consultando estado: {str(e)}")
            if not poll:
                return None
            
            print(f"Reintentando en {interval} segundos...")
            time.sleep(interval)
            attempts += 1
            
            if attempts >= max_attempts:
                print("Número máximo de intentos alcanzado")
                return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Iniciar y monitorear investigación de competidores")
    parser.add_argument("ngrok_url", help="URL base de ngrok (ej: https://abcd1234.ngrok.io)")
    parser.add_argument("business_id", help="ID del negocio para analizar competidores")
    parser.add_argument("--prompt", default="Analiza los principales competidores de este negocio, enfocándote en sus fortalezas y debilidades", 
                        help="Prompt para la búsqueda")
    parser.add_argument("--check", help="ID de solicitud para verificar estado")
    parser.add_argument("--poll", action="store_true", help="Consultar estado continuamente hasta completar")
    
    args = parser.parse_args()
    
    if args.check:
        # Solo consultar el estado
        check_research_status(args.ngrok_url, args.check, args.poll)
    else:
        # Iniciar nueva investigación
        request_id = start_competitor_research(args.ngrok_url, args.business_id, args.prompt)
        
        # Si se solicitó polling, consultar estado
        if request_id and args.poll:
            print("\nConsultando estado de la investigación...")
            check_research_status(args.ngrok_url, request_id, True) 