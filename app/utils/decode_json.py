import json
import re
import logging
from typing import Dict, Any, Optional, Tuple
import os
from datetime import datetime

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


def save_problematic_content(content: str, error_type: str = "unknown"):
    """Guarda contenido problemático para análisis posterior"""
    try:
        # Crear directorio de debugging si no existe
        debug_dir = "/tmp/noit_debug"
        os.makedirs(debug_dir, exist_ok=True)
        
        # Crear nombre de archivo único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{debug_dir}/raw_content_{error_type}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Error Type: {error_type}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Content Length: {len(content)}\n")
            f.write("="*50 + "\n")
            f.write(content)
        
        logger.info(f"Contenido problemático guardado en: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error guardando contenido problemático: {e}")
        return None


def fix_escaped_quotes(json_text: str) -> str:
    """Corrige comillas dobles escapadas como "" que deberían ser " """
    try:
        # Detectar y corregir patrón de comillas dobles escapadas
        # Patrón: ""palabra"" -> "palabra"
        json_text = re.sub(r'""([^"]*?)""', r'"\1"', json_text)
        
        # También manejar casos donde hay comillas mixtas
        # Patrón: "palabra" donde las comillas externas están duplicadas
        json_text = re.sub(r'""([^"]*?)"([^"]*?)"([^"]*?)""', r'"\1"\2"\3"', json_text)
        
        return json_text
    except Exception as e:
        logger.debug(f"Error corrigiendo comillas escapadas: {e}")
        return json_text


def fix_dot_separated_json(json_text: str) -> str:
    """Corrige JSON que usa punto+espacio como separador en lugar de comas"""
    try:
        # Remover puntos al inicio de estructuras JSON
        # Patrón: {. → {
        json_text = re.sub(r'\{\.\s*', '{', json_text)
        # Patrón: [. → [
        json_text = re.sub(r'\[\.\s*', '[', json_text)
        
        # Remover puntos al final antes de cierres
        # Patrón: '. } → ' }
        json_text = re.sub(r"(['\"])\.\s*\}", r'\1}', json_text)
        # Patrón: '. ] → ' ]
        json_text = re.sub(r"(['\"])\.\s*\]", r'\1]', json_text)
        # Patrón: number. } → number }
        json_text = re.sub(r'(\d+)\.\s*\}', r'\1}', json_text)
        json_text = re.sub(r'(\d+)\.\s*\]', r'\1]', json_text)
        # Patrón: null. } → null }
        json_text = re.sub(r'(null)\.\s*\}', r'\1}', json_text)
        json_text = re.sub(r'(null)\.\s*\]', r'\1]', json_text)
        
        # Patrón: 'field': 'value',. 'next_field' → 'field': 'value', 'next_field'
        # Primero reemplazar patrones `,. ` con `, `
        json_text = re.sub(r',\.\s+', ', ', json_text)
        
        # Luego reemplazar patrones `'. ` que no son parte de URLs o valores de texto
        # Buscar patrones como 'value',. 'key' o number,. 'key'
        json_text = re.sub(r"(['\"])\.\s+(['\"])", r'\1, \2', json_text)
        json_text = re.sub(r'(\d+)\.\s+([\'"])', r'\1, \2', json_text)
        json_text = re.sub(r'(null)\.\s+([\'"])', r'\1, \2', json_text)
        json_text = re.sub(r'(true|false)\.\s+([\'"])', r'\1, \2', json_text)
        
        # Manejar patrones de objetos: },. { → }, {
        json_text = re.sub(r'\}\.\s+\{', '}, {', json_text)
        
        # Manejar patrones de arrays: ],. [ → ], [
        json_text = re.sub(r'\]\.\s+\[', '], [', json_text)
        
        # Manejar final de objetos: },. } → }, }
        json_text = re.sub(r'\}\.\s+\}', '}, }', json_text)
        
        # **NUEVOS PATRONES** para manejar puntos sobrantes al final
        # Patrón: }. ]. → }]
        json_text = re.sub(r'\}\.\s*\]', '}]', json_text)
        # Patrón: ]. }. → ]}
        json_text = re.sub(r'\]\.\s*\}', ']}', json_text)
        # Patrón final: final con punto: algo}. → algo}
        json_text = re.sub(r'([}\]])\.\s*$', r'\1', json_text)
        # Patrón: múltiples puntos sobrantes ]. }. → ]}
        json_text = re.sub(r'\]\.\s*\}\.\s*', ']}', json_text)
        
        return json_text
    except Exception as e:
        logger.debug(f"Error corrigiendo JSON con puntos: {e}")
        return json_text


def _clean_json_text(json_text: str) -> str:
    """Limpia el texto JSON de caracteres problemáticos comunes"""
    # Remover caracteres de control y caracteres no imprimibles
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_text)
    
    # Primero corregir comillas dobles escapadas ANTES de convertir simples a dobles
    cleaned = fix_escaped_quotes(cleaned)
    
    # Corregir formato con puntos como separadores
    cleaned = fix_dot_separated_json(cleaned)
    
    # Convertir comillas simples a dobles de manera inteligente (solo si no hay dobles válidas)
    if '"' not in cleaned or cleaned.count("'") > cleaned.count('"'):
        cleaned = convert_single_to_double_quotes(cleaned)
    
    # Remover caracteres de escape extra comunes
    cleaned = cleaned.replace('\\"', '"')
    cleaned = cleaned.replace('\\n', '\n')
    cleaned = cleaned.replace('\\t', '\t')
    cleaned = cleaned.replace('\\r', '\r')
    
    # Normalizar espacios múltiples pero preservar estructura
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    
    # Limpiar espacios alrededor de delimitadores JSON
    cleaned = re.sub(r'\s*([{}[\],:]+)\s*', r'\1', cleaned)
    
    # Pero asegurar un espacio después de : y ,
    cleaned = re.sub(r'([,:])([^\s])', r'\1 \2', cleaned)
    
    return cleaned.strip()


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
    
    # Logging detallado para debugging
    logger.info(f"Procesando texto raw de {len(raw_text)} caracteres")
    logger.debug(f"Primeros 200 caracteres: {raw_text[:200]}")
    logger.debug(f"Últimos 200 caracteres: {raw_text[-200:]}")
    
    # Detectar patrones problemáticos
    has_escaped_quotes = '""' in raw_text
    has_single_quotes = "'" in raw_text
    has_double_quotes = '"' in raw_text
    has_backticks = "```" in raw_text
    has_dot_separators = ',. ' in raw_text or "'." in raw_text
    
    logger.info(f"Análisis de patrones - Escaped quotes: {has_escaped_quotes}, Single: {has_single_quotes}, Double: {has_double_quotes}, Backticks: {has_backticks}, Dot separators: {has_dot_separators}")
    
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
    
    # Si llegamos aquí, guardar el contenido para análisis
    save_problematic_content(raw_text, "extraction_failed")
    
    logger.warning("No se pudo extraer JSON con métodos automáticos, se requiere LLM")
    return None, True


def fix_malformed_json(json_text: str) -> str:
    """Intenta reparar JSON malformado común"""
    try:
        # Manejar valores Python-style (None, True, False)
        json_text = re.sub(r'\bnull\b', 'null', json_text)  # Ya está bien
        json_text = re.sub(r'\bNone\b', 'null', json_text)  # Python None -> JSON null
        json_text = re.sub(r'\bTrue\b', 'true', json_text)   # Python True -> JSON true
        json_text = re.sub(r'\bFalse\b', 'false', json_text) # Python False -> JSON false
        
        # Reparar comas faltantes después de valores
        json_text = re.sub(r'(["\d\}\]])(\s*\n\s*)(["\{])', r'\1,\2\3', json_text)
        
        # Reparar comas extra antes de llaves de cierre
        json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
        
        # Reparar comillas faltantes en claves (para el caso donde no se aplicó la conversión correctamente)
        json_text = re.sub(r'([{\[,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_text)
        
        # Reparar valores sin comillas que deberían tenerlas (excepto números, booleanos y null)
        json_text = re.sub(r':\s*([^",\[\{\d\s\-][^",\[\{,}\]]*?)(\s*[,\}\]])', r': "\1"\2', json_text)
        
        # Reparar arrays mal formados
        json_text = re.sub(r'\[\s*,', '[', json_text)
        json_text = re.sub(r',\s*\]', ']', json_text)
        
        # Reparar objetos mal formados
        json_text = re.sub(r'\{\s*,', '{', json_text)
        json_text = re.sub(r',\s*\}', '}', json_text)
        
        # Reparar espacios dentro de strings que pueden romper el JSON
        json_text = re.sub(r'"\s*([^"]*?)\s*"', lambda m: f'"{m.group(1).strip()}"', json_text)
        
        return json_text
    except Exception as e:
        logger.debug(f"Error reparando JSON: {e}")
        return json_text


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
        
        for i, pattern in enumerate(patterns):
            logger.debug(f"Probando patrón {i+1}: {pattern}")
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(1).strip()
                logger.debug(f"JSON encontrado con patrón {i+1}, longitud: {len(json_text)}")
                logger.debug(f"JSON extraído (primeros 100 chars): {json_text[:100]}")
                
                # Limpiar el JSON antes de parsearlo
                json_text = _clean_json_text(json_text)
                
                # Intentar parsear directamente
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.debug(f"Primer intento de parsing falló: {e}")
                    # Intentar reparar y parsear de nuevo
                    fixed_json = fix_malformed_json(json_text)
                    logger.debug(f"JSON reparado (primeros 100 chars): {fixed_json[:100]}")
                    return json.loads(fixed_json)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"Error extrayendo JSON de backticks: {e}")
    return None


def _extract_json_from_braces(text: str) -> Optional[Dict[str, Any]]:
    """Extrae JSON buscando las llaves principales del objeto"""
    try:
        # Buscar desde la primera { hasta la última }
        start_idx = text.find('{')
        if start_idx == -1:
            logger.debug("No se encontró llave de apertura {")
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
            logger.debug(f"JSON encontrado por llaves, longitud: {len(json_text)}")
            logger.debug(f"JSON extraído (primeros 100 chars): {json_text[:100]}")
            
            # Limpiar el JSON antes de parsearlo
            json_text = _clean_json_text(json_text)
            
            # Intentar parsear directamente
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.debug(f"Primer intento de parsing falló: {e}")
                # Intentar reparar y parsear de nuevo
                fixed_json = fix_malformed_json(json_text)
                logger.debug(f"JSON reparado (primeros 100 chars): {fixed_json[:100]}")
                return json.loads(fixed_json)
        else:
            logger.debug("No se encontró llave de cierre correspondiente")
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
        
        # Limpiar el JSON
        cleaned = _clean_json_text(cleaned)
        
        logger.debug(f"Texto limpio para parsing directo (primeros 100 chars): {cleaned[:100]}")
        
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
        
        for i, pattern in enumerate(patterns):
            logger.debug(f"Probando patrón flexible {i+1}: {pattern}")
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                json_text = match.group(0)
                logger.debug(f"JSON encontrado con patrón flexible {i+1}, longitud: {len(json_text)}")
                
                # Si solo capturó la parte de competitors, envolver en objeto
                if json_text.strip().startswith('"competitors"'):
                    json_text = '{' + json_text + '}'
                
                # Limpiar el JSON
                json_text = _clean_json_text(json_text)
                return json.loads(json_text)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.debug(f"Error en extracción flexible: {e}")
    return None


def convert_single_to_double_quotes(json_text: str) -> str:
    """Convierte comillas simples a dobles de manera inteligente para JSON"""
    try:
        # Primero, proteger las comillas simples que están dentro de strings con comillas dobles
        # Patrón para encontrar strings con comillas dobles que contengan comillas simples
        protected_strings = []
        
        def protect_string(match):
            protected_strings.append(match.group(0))
            return f"__PROTECTED_STRING_{len(protected_strings)-1}__"
        
        # Proteger strings que ya usan comillas dobles
        json_text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', protect_string, json_text)
        
        # Ahora convertir todas las comillas simples restantes a dobles
        # Esto incluye claves y valores que usan comillas simples
        json_text = json_text.replace("'", '"')
        
        # Restaurar las strings protegidas
        for i, protected in enumerate(protected_strings):
            json_text = json_text.replace(f"__PROTECTED_STRING_{i}__", protected)
        
        return json_text
    except Exception as e:
        logger.debug(f"Error convirtiendo comillas: {e}")
        return json_text