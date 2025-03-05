from typing import Dict, List
import json

def parse_json_with_llm(lang, raw_response):
    if lang == 'es':
        return f"""
        Convierte esta respuesta en un JSON válido:

        Requisitos:
        - Sólo toma lo que hay dentro de lo que está como ```JSON```
        - Asegura que el JSON sea válido

        Respuesta original:
        {raw_response}
        """
    else:
        return f"""
        Convert this response into valid JSON:

        Requirements:
        - Only take what's inside the ```JSON```
        - Ensure the JSON is valid

        Original response:
        {raw_response}
        """


def create_parsing_prompt_competitors(lang, raw_response):
    if lang == 'es':
        return f"""
        Convierte esta respuesta en un JSON válido:
        
        Requisitos:
        - Usar keys del inglés
        - Validar URLs
        - Asegurar scores entre 1-100
        
        Respuesta original:
        {raw_response}
        
        Formato requerido:
        {{
            "competitors": [
            {{
                "full_name": "string",
                "key_feature": "string",
                "website": "url",
                "instagram_url": "handle",
                "facebook_url": "handle",
                "linkedin_url": "handle",
                "x_url": "handle",
                "youtube_url": "handle",
                "tiktok_url": "handle",
                "similarity_score": number
            }}
            ]
        }}

        IMPORTANTE:
        - Devuelve ÚNICAMENTE el JSON sin comentarios
        - Asegura que similarity_score sea número
        - Valida que las URLs sean correctas
        - Asegurate que los keys del json estén en inglés
        
        """
    else:
        return f"""
        Convert this response into valid JSON:
        
        Requirements:
        - Use English keys
        - Validate URLs
        - Ensure scores 1-100
        
        Original response:
        {raw_response}
        
        Required format:
        {{
            "competitors": [
            {{
                "full_name": "string",
                "key_feature": "string",
                "website": "url",
                "instagram_url": "handle",
                "facebook_url": "handle",
                "linkedin_url": "handle",
                "x_url": "handle",
                "youtube_url": "handle",
                "tiktok_url": "handle",
                "similarity_score": number
            }}
            ]
        }}

        IMPORTANT:
        - Return ONLY the JSON without comments
        - Ensure that similarity_score is a number
        - Validate that the URLs are correct
        """
    

def create_competitor_details_query(lang, business_details, competitor: Dict) -> str:
    """Crea el prompt para buscar detalles específicos de un competidor"""
    competitor_name = competitor.get('full_name', '')
    competitor_website = competitor.get('website', '')
    key_feature = competitor.get('key_feature', '')
    
    if lang == 'es':
        prompt = f"""

        En base a esta idea de negocio:

        {business_details}

        Necesito información detallada sobre este competidor "{competitor_name}".
        
        Website reportado: {competitor_website}

        Marca especializada en: {key_feature}
        
        Por favor encuentra y extrae la siguiente información:
        1. Verifica si el sitio web proporcionado es correcto, si no, proporciona el correcto
        2. Característica principal o propuesta de valor única
        3. Enlaces de redes sociales (usuarios/handles):
        - Instagram
        - Facebook
        - LinkedIn
        - Twitter/X
        - YouTube
        - TikTok
        
        Si no puedes encontrar alguna información, deja el campo en blanco.
        Usa fuentes oficiales y actualizadas. Valida cuidadosamente la información.

        Asegurate que estas buscando un competidor para la idea de negocio proporcionada.

        Formato de salida en JSON:
        """
    else:
        prompt = f"""
        I need detailed information about the competitor "{competitor_name}".
        
        Reported website: {competitor_website}

        Specialized brand in: {key_feature}
        
        Please find and extract the following information:
        1. Verify if the provided website is correct, if not, provide the correct one
        2. Key feature or unique value proposition
        3. Social media links (usernames/handles):
        - Instagram
        - Facebook
        - LinkedIn
        - Twitter/X
        - YouTube
        - TikTok
        
        If you cannot find some information, leave the field blank.
        Use official and up-to-date sources. Carefully validate the information.

        Output format in JSON:
        """
    
    prompt += """
    \n
    {
        "website": "url",
        "instagram_url": "handle",
        "facebook_url": "handle",
        "linkedin_url": "handle",
        "x_url": "handle",
        "youtube_url": "handle",
        "tiktok_url": "handle",
    }

    """

    if lang == 'es':
        prompt += f"""
        \n
        IMPORTANTE:
        - Devuelve ÚNICAMENTE el JSON sin comentarios
        - Valida que las URLs sean correctas
        """
    else:
        prompt += f"""
        \n
        IMPORTANT:
        - Return ONLY the JSON without comments
        - Validate that the URLs are correct
        """

    return prompt


def create_research_query(lang, business_details, prompt_search: str) -> str:
    if lang == 'es':
        base_query = f"""
        {prompt_search}
        \n
        {business_details}
        """

        query = base_query + """
        \n
        Requisitos:
        1. Listar máximo 20 competidores
        2. Usar SIEMPRE keys en inglés
        3. Valores pueden ser en español
        4. Formato JSON:

        {
        "competitors": [
            {
            "full_name": "string", # Nombre Completo del Competidor
            "key_feature": "string", # Característica principal/clave del competidor (Propuesta de valor)
            "website": "url", # URL del sitio web
            "similarity_score": 1-100 # Porcentaje de similitud con la idea de negocio
            }
            ]
        }

        Evita incluir comentarios adicionales en el JSON de salida.
        """
    else:
        base_query = f"""
        {prompt_search}
        \n
        {business_details}
        """

        query = base_query + """
        \n
        Requirements:
        1. List top 20 competitors
        2. Use English keys
        3. JSON Format:
        {
            "competitors": [
                {
                "full_name": "string", # Competitor's Full Name
                "key_feature": "string", # Competitor's Key Feature (Value Proposition)
                "website": "url", # Competitor's Website URL
                "similarity_score": 1-100 # Similarity score with the business idea
                }
            ]
        }

        Avoid adding extra comments in the output JSON.
        """
    
    return query

def create_analysis_prompt(lang, business_model) -> str:
    if lang == 'es':
        return f"""
        Eres un investigador doctoral (PhD) especializado en Marketing y Administración de Empresas.
        La tarea consiste en generar un conjunto de preguntas e indicaciones que guíen la
        elaboración de un “análisis de competencia”.

        Las preguntas las vas a hacer con el objetivo de evaluar a un competidor directo de la empresa

        Genera 15-20 preguntas de análisis competitivo basadas en el siguiente modelo de negocio.
        Requisitos:
        - Las preguntas deben poder responderse con información pública en el sitio web
        - Enfocarse en: posicionamiento de marca, estrategia de marketing, oferta de productos
        - Evitar preguntas que requieran datos financieros internos
        
        Modelo de negocio: {json.dumps(vars(business_model))}
        """
    else:
        return f"""
        Generate 15-20 competitive analysis questions based on this business model.
        Requirements:
        - Questions must be answerable through public information (websites, social media)
        - Focus on: brand positioning, marketing strategy, product offering
        - Avoid questions requiring internal financial data
        
        Business Model: {json.dumps(vars(business_model))}
        """


def create_cleaning_prompt(lang, questions: List[str]) -> str:
    if lang == 'es':
        return f"""
        Limpia y organiza estas preguntas de análisis competitivo:
        1. Eliminar duplicados
        2. Asegurar que sean accionables con datos públicos de página web
        3. Ordenar por importancia estratégica
        4. Limitar a máximo 15 preguntas

        Dame sólo las preguntas, evita añadir anotaciones o comentarios.
        
        Preguntas: {json.dumps(questions)}
        """
    else:
        return f"""
        Clean and organize these competitive analysis questions:
        1. Remove duplicates
        2. Ensure they're actionable with public data
        3. Sort by strategic importance
        4. Limit to 15 questions max
        
        Questions: {json.dumps(questions)}
        """