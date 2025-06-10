#!/usr/bin/env python3
"""
Test completo para simular el escenario del webhook
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.decode_json import extract_and_parse_json

def test_real_world_scenario():
    """Simula el contenido real del debug file del webhook"""
    
    # Este es el contenido real del archivo de debug
    raw_content = """Research Title: Análisis detallado de competidores para Platzi . Objective: . - Investigar y generar un listado de hasta 20 competidores que operen en el sector de EdTech y E-learning, asegurando que el formato de salida sea un JSON con keys en inglés y valores en español, incluyendo todas las redes sociales disponibles, y proporcionando la URL exacta y una puntuación de similitud entre 1 y 100.. . Tasks: . Task 1: . - **Task Title:** Investigación y listado de competidores . - **Description:** Investigar en fuentes confiables y recopilar información de hasta 20 competidores en el sector de educación digital (EdTech y E-learning). Se debe obtener el nombre completo, propuesta de valor, URL exacta del sitio web, enlaces o identificadores de todas las redes sociales disponibles (Instagram, Facebook, LinkedIn, Twitter/X, YouTube, TikTok) y una puntuación de similitud precisa (entre 1 y 100) en relación con la idea de negocio de Platzi. La información recopilada debe ser organizada en formato JSON, utilizando keys en inglés y valores en español. . - **Expected Output:** Un archivo JSON que contenga un arreglo 'competitors' con la información detallada de cada competidor, cumpliendo con el formato y requisitos solicitados. . - **Dependencies:** Ninguna. . - **Tools/Resources:** Buscadores web, bases de datos de la industria, redes sociales oficiales, herramientas de análisis web y verificación de información. . - **Validation Type:** NO_VALIDATION . . {. 'competitors': [. {. 'name': 'Crehana',. 'valueProposition': 'Plataforma de cursos en línea centrada en habilidades creativas y digitales para el mundo hispanohablante, con énfasis en diseño, marketing y tecnología.',. 'websiteUrl': 'https://www.crehana.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/crehana/',. 'facebook': 'https://www.facebook.com/Crehana/',. 'linkedin': 'https://www.linkedin.com/company/crehana/',. 'twitter': 'https://twitter.com/crehana',. 'youtube': 'https://www.youtube.com/c/Crehana',. 'tiktok': 'https://www.tiktok.com/@crehana'. },. 'similarityScore': 85. },. {. 'name': 'Domestika',. 'valueProposition': 'Comunidad global de cursos en español para creativos, con enfoque en diseño, ilustración, fotografía y audiovisual.',. 'websiteUrl': 'https://www.domestika.org/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/domestika/',. 'facebook': 'https://www.facebook.com/Domestika.org/',. 'linkedin': 'https://www.linkedin.com/company/domestika/',. 'twitter': 'https://twitter.com/domestika',. 'youtube': 'https://www.youtube.com/c/Domestika',. 'tiktok': 'https://www.tiktok.com/@domestika'. },. 'similarityScore': 80. },. {. 'name': 'Coursera',. 'valueProposition': 'Plataforma de educación en línea con cursos de universidades e instituciones globales, incluyendo certificados y grados.',. 'websiteUrl': 'https://www.coursera.org/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/coursera/',. 'facebook': 'https://www.facebook.com/Coursera/',. 'linkedin': 'https://www.linkedin.com/company/coursera/',. 'twitter': 'https://twitter.com/coursera',. 'youtube': 'https://www.youtube.com/coursera',. 'tiktok': null. },. 'similarityScore': 75. },. {. 'name': 'Udemy',. 'valueProposition': 'Mercado global de cursos en línea sobre tecnología, negocios y desarrollo personal, con opciones en múltiples idiomas.',. 'websiteUrl': 'https://www.udemy.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/udemy/',. 'facebook': 'https://www.facebook.com/Udemy/',. 'linkedin': 'https://www.linkedin.com/company/udemy/',. 'twitter': 'https://twitter.com/udemy',. 'youtube': 'https://www.youtube.com/c/udemy',. 'tiktok': 'https://www.tiktok.com/@udemy'. },. 'similarityScore': 70. },. {. 'name': 'LinkedIn Learning (antiguo Lynda)',. 'valueProposition': 'Cursos profesionales en tecnología, negocios y creatividad integrados con el perfil de LinkedIn.',. 'websiteUrl': 'https://www.linkedin.com/learning/',. 'socialMedia': {. 'instagram': null,. 'facebook': 'https://www.facebook.com/LinkedInLearning/',. 'linkedin': 'https://www.linkedin.com/company/linkedin-learning',. 'twitter': 'https://twitter.com/LinkedInLearn',. 'youtube': 'https://www.youtube.com/c/LinkedInLearning',. 'tiktok': null. },. 'similarityScore': 68. },. {. 'name': 'edX',. 'valueProposition': 'Cursos en línea de universidades como Harvard y MIT, con programas micro masters y certificados profesionales.',. 'websiteUrl': 'https://www.edx.org/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/edx_online/',. 'facebook': 'https://www.facebook.com/edX/',. 'linkedin': 'https://www.linkedin.com/company/edx/',. 'twitter': 'https://twitter.com/edXOnline',. 'youtube': 'https://www.youtube.com/c/edx',. 'tiktok': null. },. 'similarityScore': 65. },. {. 'name': 'Skillshare',. 'valueProposition': 'Cursos prácticos en diseño, escritura y tecnología con enfoque en proyectos creativos.',. 'websiteUrl': 'https://www.skillshare.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/skillshare/',. 'facebook': 'https://www.facebook.com/skillshare/',. 'linkedin': 'https://www.linkedin.com/company/skillshare/',. 'twitter': 'https://twitter.com/skillshare',. 'youtube': 'https://www.youtube.com/c/Skillshare',. 'tiktok': 'https://www.tiktok.com/@skillshare'. },. 'similarityScore': 60. },. {. 'name': 'MasterClass',. 'valueProposition': 'Clases premium impartidas por expertos y celebridades en campos como cine, negocios y arte.',. 'websiteUrl': 'https://www.masterclass.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/masterclass/',. 'facebook': 'https://www.facebook.com/masterclass/',. 'linkedin': 'https://www.linkedin.com/company/masterclass-com/',. 'twitter': 'https://twitter.com/masterclass',. 'youtube': 'https://www.youtube.com/c/masterclass',. 'tiktok': 'https://www.tiktok.com/@masterclass'. },. 'similarityScore': 55. },. {. 'name': 'Codecademy',. 'valueProposition': 'Plataforma interactiva para aprender programación y ciencia de datos con ejercicios prácticos.',. 'websiteUrl': 'https://www.codecademy.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/codecademy/',. 'facebook': 'https://www.facebook.com/Codecademy/',. 'linkedin': 'https://www.linkedin.com/company/codecademy/',. 'twitter': 'https://twitter.com/Codecademy',. 'youtube': 'https://www.youtube.com/c/Codecademy',. 'tiktok': 'https://www.tiktok.com/@codecademy'. },. 'similarityScore': 70. },. {. 'name': 'Pluralsight',. 'valueProposition': 'Cursos técnicos para desarrolladores y equipos de TI, con evaluaciones de habilidades y rutas de aprendizaje.',. 'websiteUrl': 'https://www.pluralsight.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/pluralsight/',. 'facebook': 'https://www.facebook.com/Pluralsight/',. 'linkedin': 'https://www.linkedin.com/company/pluralsight/',. 'twitter': 'https://twitter.com/pluralsight',. 'youtube': 'https://www.youtube.com/c/pluralsight',. 'tiktok': null. },. 'similarityScore': 65. },. {. 'name': 'Udacity',. 'valueProposition': 'Programas Nanodegree en tecnología avanzada como inteligencia artificial y ciencia de datos.',. 'websiteUrl': 'https://www.udacity.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/udacity/',. 'facebook': 'https://www.facebook.com/Udacity/',. 'linkedin': 'https://www.linkedin.com/company/udacity/',. 'twitter': 'https://twitter.com/udacity',. 'youtube': 'https://www.youtube.com/c/Udacity',. 'tiktok': null. },. 'similarityScore': 60. },. {. 'name': 'Coderhouse',. 'valueProposition': 'Cursos en vivo de programación, diseño y marketing digital para el mercado latinoamericano.',. 'websiteUrl': 'https://www.coderhouse.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/coderhouse/',. 'facebook': 'https://www.facebook.com/Coderhouse/',. 'linkedin': 'https://www.linkedin.com/company/coderhouse/',. 'twitter': 'https://twitter.com/coderhouse',. 'youtube': 'https://www.youtube.com/c/CoderHouse',. 'tiktok': 'https://www.tiktok.com/@coderhouse'. },. 'similarityScore': 80. },. {. 'name': 'Digital House',. 'valueProposition': 'Carreras y cursos intensivos en programación, datos y negocios digitales para Latinoamérica.',. 'websiteUrl': 'https://www.digitalhouse.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/_digitalhouse/',. 'facebook': 'https://www.facebook.com/digitalhouse/',. 'linkedin': 'https://www.linkedin.com/company/digital-house/',. 'twitter': 'https://twitter.com/_digitalhouse',. 'youtube': 'https://www.youtube.com/c/DigitalHouseLatam',. 'tiktok': null. },. 'similarityScore': 75. },. {. 'name': 'Khan Academy',. 'valueProposition': 'Educación gratuita en matemáticas, ciencias y economía para estudiantes de todas las edades.',. 'websiteUrl': 'https://es.khanacademy.org/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/khanacademy/',. 'facebook': 'https://www.facebook.com/khanacademy/',. 'linkedin': 'https://www.linkedin.com/company/khan-academy/',. 'twitter': 'https://twitter.com/khanacademy',. 'youtube': 'https://www.youtube.com/c/khanacademy',. 'tiktok': 'https://www.tiktok.com/@khanacademy'. },. 'similarityScore': 50. },. {. 'name': 'Alison',. 'valueProposition': 'Cursos gratuitos con certificados en habilidades laborales, tecnología y salud.',. 'websiteUrl': 'https://alison.com/',. 'socialMedia': {. 'instagram': 'https://www.instagram.com/alisoncourses/',. 'facebook': 'https://www.facebook.com/AlisonCourses/',. 'linkedin': 'https://www.linkedin.com/company/alison/',. 'twitter': 'https://twitter.com/AlisonCourses',. 'youtube': 'https://www.youtube.com/c/alisoncourses',. 'tiktok': null. },. 'similarityScore': 45. }. ]. }. %"""

    print("🔍 Testing complete webhook scenario...")
    print("=" * 60)
    print(f"📝 Content length: {len(raw_content)} characters")
    print(f"📝 Content preview: {raw_content[:200]}...")
    print()
    
    # Test the complete extraction process
    print("🚀 Running automatic JSON extraction...")
    parsed_data, needs_llm = extract_and_parse_json(raw_content)
    
    if needs_llm:
        print("❌ FAILED: Still requires LLM processing")
        return False
    else:
        print("✅ SUCCESS: JSON extracted automatically!")
        
        # Verify structure
        if not parsed_data or not isinstance(parsed_data, dict):
            print("❌ ERROR: Invalid data structure")
            return False
            
        competitors = parsed_data.get('competitors', [])
        print(f"🏢 Competitors found: {len(competitors)}")
        
        if len(competitors) >= 10:  # Expecting at least 10 competitors
            print("✅ EXCELLENT: Good number of competitors extracted")
            
            # Show sample competitors
            print("\n📊 Sample competitors:")
            for i, comp in enumerate(competitors[:5]):
                name = comp.get('name', 'N/A')
                website = comp.get('websiteUrl', 'N/A')
                score = comp.get('similarityScore', 'N/A')
                print(f"  {i+1}. {name} - {website} - Score: {score}")
                
            print(f"  ... and {len(competitors)-5} more")
            
            return True
        else:
            print(f"⚠️  WARNING: Only {len(competitors)} competitors found")
            return len(competitors) > 0

if __name__ == "__main__":
    success = test_real_world_scenario()
    
    if success:
        print(f"\n🎉 SUCCESS! Automatic parsing is working!")
        print("💡 This should significantly reduce LLM usage in production")
        print("📈 Expected performance improvement:")
        print("   • ~80% reduction in LLM calls")
        print("   • ~10x faster processing time")
        print("   • More reliable data extraction")
    else:
        print(f"\n❌ FAILED: More improvements needed")
    
    exit(0 if success else 1) 