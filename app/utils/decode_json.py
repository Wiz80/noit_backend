import json
import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def clean_json_encoding(json_data):
    if isinstance(json_data, str):
        # Maneja las secuencias de escape unicode y los caracteres especiales
        return json_data.encode('raw_unicode_escape').decode('unicode_escape')
    elif isinstance(json_data, dict):
        return {k: clean_json_encoding(v) for k, v in json_data.items()}
    elif isinstance(json_data, list):
        return [clean_json_encoding(item) for item in json_data]
    else:
        return json_data


def extract_and_parse_json(raw_text: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Intenta extraer y parsear JSON de un texto raw usando múltiples estrategias.
    
    Args:
        raw_text (str): Texto raw que contiene JSON
        
    Returns:
        Tuple[Optional[Dict[str, Any]], bool]: (datos_parseados, necesita_llm)
        - datos_parseados: Diccionario con el JSON parseado o None si falló
        - necesita_llm: True si se requiere parsing con LLM, False si se parseó exitosamente
    """
    if not raw_text or not isinstance(raw_text, str):
        logger.warning("Texto raw vacío o no es string")
        return None, True
    
    # Estrategia 1: Buscar JSON entre triple backticks
    json_data = _extract_json_from_backticks(raw_text)
    if json_data:
        logger.info("JSON extraído exitosamente de triple backticks")
        return json_data, False
    
    # Estrategia 2: Buscar JSON entre llaves principales
    json_data = _extract_json_from_braces(raw_text)
    if json_data:
        logger.info("JSON extraído exitosamente de llaves principales")
        return json_data, False
    
    # Estrategia 3: Limpiar texto y intentar parsear directo
    json_data = _clean_and_parse_direct(raw_text)
    if json_data:
        logger.info("JSON parseado exitosamente después de limpieza directa")
        return json_data, False
    
    # Estrategia 4: Buscar patrones JSON más flexibles
    json_data = _extract_json_flexible(raw_text)
    if json_data:
        logger.info("JSON extraído exitosamente con patrones flexibles")
        return json_data, False
    
    logger.warning("No se pudo extraer JSON con métodos automáticos, se requiere LLM")
    return None, True


def _extract_json_from_backticks(text: str) -> Optional[Dict[str, Any]]:
    """Extrae JSON de entre triple backticks"""
    try:
        # Patrón para encontrar ```json ... ``` o ``` ... ```
        patterns = [
            r'```json\s*\n(.*?)\n```',
            r'```\s*\n(.*?)\n```',
            r'```json(.*?)```',
            r'```(.*?)```'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(1).strip()
                return json.loads(json_text)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"Error extrayendo JSON de backticks: {e}")
    return None


def _extract_json_from_braces(text: str) -> Optional[Dict[str, Any]]:
    """Extrae JSON buscando las llaves principales del objeto"""
    try:
        # Buscar desde la primera { hasta la última }
        start_idx = text.find('{')
        if start_idx == -1:
            return None
        
        # Buscar la llave de cierre correspondiente
        brace_count = 0
        end_idx = -1
        
        for i, char in enumerate(text[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx != -1:
            json_text = text[start_idx:end_idx]
            return json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Error extrayendo JSON de llaves: {e}")
    return None


def _clean_and_parse_direct(text: str) -> Optional[Dict[str, Any]]:
    """Limpia el texto y intenta parsearlo directamente como JSON"""
    try:
        # Limpiar caracteres comunes que pueden interferir
        cleaned = text.strip()
        
        # Remover prefijos/sufijos comunes
        prefixes_to_remove = [
            "Here's the analysis:",
            "Here is the analysis:",
            "Analysis:",
            "Result:",
            "Response:",
            "JSON:",
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
        
        # Remover caracteres de escape extra
        cleaned = cleaned.replace('\\"', '"')
        cleaned = cleaned.replace('\\n', '\n')
        
        # Intentar parsear
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Error en limpieza y parsing directo: {e}")
    return None


def _extract_json_flexible(text: str) -> Optional[Dict[str, Any]]:
    """Busca JSON usando patrones más flexibles"""
    try:
        # Buscar patrones que contengan "competitors" u otros campos clave
        patterns = [
            r'"competitors_analysis"\s*:\s*{.*?"competitors"\s*:\s*\[.*?\].*?}',
            r'{.*?"competitors"\s*:\s*\[.*?\].*?}',
            r'"competitors"\s*:\s*\[.*?\]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(0)
                
                # Si solo capturó la parte de competitors, envolver en objeto
                if json_text.strip().startswith('"competitors"'):
                    json_text = '{' + json_text + '}'
                
                return json.loads(json_text)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"Error en extracción flexible: {e}")
    return None