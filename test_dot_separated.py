#!/usr/bin/env python3
"""
Script de prueba para verificar el manejo de JSON con puntos como separadores
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.decode_json import extract_and_parse_json, fix_dot_separated_json
import json

def test_dot_separated_parsing():
    # Ejemplo basado en el contenido problemático real
    raw_response = """{. 'competitors': [. {. 'name': 'Crehana',. 'valueProposition': 'Plataforma de cursos en línea centrada en habilidades creativas y digitales',. 'websiteUrl': 'https://www.crehana.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/crehana/',. 'facebook': 'https://www.facebook.com/Crehana/',. 'linkedin': 'https://www.linkedin.com/company/crehana/',. 'twitter': 'https://twitter.com/crehana',. 'youtube': 'https://www.youtube.com/c/Crehana',. 'tiktok': 'https://www.tiktok.com/@crehana'. },. 'similarityScore': 85. },. {. 'name': 'Domestika',. 'valueProposition': 'Comunidad global de cursos en español para creativos',. 'websiteUrl': 'https://www.domestika.org/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/domestika/',. 'facebook': 'https://www.facebook.com/Domestika.org/',. 'linkedin': 'https://www.linkedin.com/company/domestika/',. 'twitter': 'https://twitter.com/domestika',. 'youtube': 'https://www.youtube.com/c/Domestika',. 'tiktok': 'https://www.tiktok.com/@domestika'. },. 'similarityScore': 80. }. ]. }."""

    print("🔍 Testando parsing de JSON con puntos como separadores...")
    print("=" * 60)
    
    print("📝 Contenido original:")
    print("Primeros 200 chars:", raw_response[:200])
    print("Patrón detectado: Puntos como separadores (',. ')")
    print()
    
    # Probar paso a paso para debugging detallado
    from app.utils.decode_json import convert_single_to_double_quotes, _clean_json_text
    
    print("🔧 Paso 1: Corrección de puntos...")
    step1 = fix_dot_separated_json(raw_response)
    print("✅ Dots fixed")
    
    print("🔧 Paso 2: Conversión de comillas...")
    step2 = convert_single_to_double_quotes(step1)
    print("✅ Quotes converted")
    
    print("🔧 Paso 3: Intentando parsing...")
    try:
        parsed = json.loads(step2)
        print("✅ ÉXITO: JSON parseado correctamente!")
        
        # Verificar datos específicos
        competitors = parsed.get('competitors', [])
        print(f"🏢 Competidores encontrados: {len(competitors)}")
        
        if len(competitors) >= 2:
            print("✅ Cantidad correcta de competidores")
            for i, comp in enumerate(competitors[:2]):
                name = comp.get('name', 'N/A')
                website = comp.get('websiteUrl', 'N/A')
                score = comp.get('similarityScore', 'N/A')
                print(f"  {i+1}. {name} - {website} - Score: {score}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Error en parsing: {e}")
        print(f"Error en posición: {e.pos}")
        
        # Mostrar contexto alrededor del error
        start = max(0, e.pos - 50)
        end = min(len(step2), e.pos + 50)
        context = step2[start:end]
        error_pos = e.pos - start
        
        print("📍 Contexto del error:")
        print(f"   {context}")
        print(f"   {' ' * error_pos}^")
        print()
        
        # Buscar patrones problemáticos específicos
        print("🔍 Buscando patrones problemáticos...")
        if '. ' in step2:
            print("⚠️  Aún hay puntos+espacio en el texto")
        if "',." in step2:
            print("⚠️  Hay comillas+coma+punto")
        if '". ' in step2:
            print("⚠️  Hay comillas dobles+punto+espacio")
        
        return False

if __name__ == "__main__":
    success = test_dot_separated_parsing()
    if success:
        print("\n🎉 ¡Parser automático funcionando con puntos como separadores!")
    else:
        print("\n❌ El parser necesita más mejoras")
    
    exit(0 if success else 1) 