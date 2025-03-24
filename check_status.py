import requests
import json
import argparse
import time

def check_research_status(ngrok_url, request_id, poll=False, interval=5, max_attempts=20):
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
            if response.status_code != 200:
                print(f"Error: Código de estado {response.status_code}")
                print(response.text)
                if not poll:
                    return None
                
                print(f"Reintentando en {interval} segundos...")
                time.sleep(interval)
                attempts += 1
                continue
            
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
    parser = argparse.ArgumentParser(description="Consultar estado de investigación de competidores")
    parser.add_argument("ngrok_url", help="URL base de ngrok (ej: https://abcd1234.ngrok.io)")
    parser.add_argument("request_id", help="ID de la solicitud a consultar")
    parser.add_argument("--poll", action="store_true", help="Consultar estado continuamente hasta completar")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo entre consultas en segundos (solo con --poll)")
    parser.add_argument("--max-attempts", type=int, default=20, help="Número máximo de intentos (solo con --poll)")
    
    args = parser.parse_args()
    
    check_research_status(args.ngrok_url, args.request_id, args.poll, args.interval, args.max_attempts) 