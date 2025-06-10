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
    competitors_count = raw_response.count('"name"') + raw_response.count("'name'") + raw_response.count('name')
    
    if lang == 'es':
        return f"""
        Convierte esta respuesta en un JSON válido y COMPLETO:
        
        CRÍTICO - MANTENER TODOS LOS DATOS:
        - OBLIGATORIO: Conservar TODOS los competidores del listado original
        - He detectado aproximadamente {competitors_count} competidores en el texto
        - NO truncar, cortar o limitar la cantidad de competidores
        - Si hay 15 competidores en la entrada, DEBES devolver los 15
        
        Requisitos técnicos:
        - Usar keys en inglés exactamente como se especifica
        - Convertir nombres de campos según el mapeo requerido
        - Validar URLs correctamente
        - Asegurar scores entre 1-100
        - Manejar valores null apropiadamente
        
        MAPEO DE CAMPOS OBLIGATORIO:
        - "name" → "competitor_name"
        - "valueProposition" → "key_feature" 
        - "websiteUrl" → "website"
        - "socialMedia.instagram" → "instagram_url"
        - "socialMedia.facebook" → "facebook_url"
        - "socialMedia.linkedin" → "linkedin_url"
        - "socialMedia.twitter" → "x_url"
        - "socialMedia.youtube" → "youtube_url"
        - "socialMedia.tiktok" → "tiktok_url"
        - "similarityScore" → "similarity_score"
        
        Respuesta original:
        {raw_response}
        
        Formato requerido (TODOS los competidores):
        {{
            "competitors": [
            {{
                "competitor_name": "string",
                "key_feature": "string",
                "website": "url",
                "instagram_url": "url o null",
                "facebook_url": "url o null",
                "linkedin_url": "url o null",
                "x_url": "url o null",
                "youtube_url": "url o null",
                "tiktok_url": "url o null",
                "similarity_score": number
            }}
            ]
        }}

        IMPORTANTE:
        - Devuelve ÚNICAMENTE el JSON sin comentarios
        - CONSERVA TODOS los competidores (NO menos de {max(1, competitors_count-2)})
        - Asegura que similarity_score sea número
        - Valida que las URLs sean correctas o null
        - Asegurate que los keys del json estén exactamente como se especifica
        
        """
    else:
        return f"""
        Convert this response into valid and COMPLETE JSON:
        
        CRITICAL - MAINTAIN ALL DATA:
        - MANDATORY: Preserve ALL competitors from the original list
        - I detected approximately {competitors_count} competitors in the text
        - DO NOT truncate, cut, or limit the number of competitors
        - If there are 15 competitors in input, you MUST return all 15
        
        Technical requirements:
        - Use English keys exactly as specified
        - Convert field names according to required mapping
        - Validate URLs correctly
        - Ensure scores 1-100
        - Handle null values appropriately
        
        MANDATORY FIELD MAPPING:
        - "name" → "competitor_name"
        - "valueProposition" → "key_feature"
        - "websiteUrl" → "website"
        - "socialMedia.instagram" → "instagram_url"
        - "socialMedia.facebook" → "facebook_url"
        - "socialMedia.linkedin" → "linkedin_url"
        - "socialMedia.twitter" → "x_url"
        - "socialMedia.youtube" → "youtube_url"
        - "socialMedia.tiktok" → "tiktok_url"
        - "similarityScore" → "similarity_score"
        
        Original response:
        {raw_response}
        
        Required format (ALL competitors):
        {{
            "competitors": [
            {{
                "competitor_name": "string",
                "key_feature": "string",
                "website": "url",
                "instagram_url": "url or null",
                "facebook_url": "url or null",
                "linkedin_url": "url or null",
                "x_url": "url or null",
                "youtube_url": "url or null",
                "tiktok_url": "url or null",
                "similarity_score": number
            }}
            ]
        }}

        IMPORTANT:
        - Return ONLY the JSON without comments
        - PRESERVE ALL competitors (NO less than {max(1, competitors_count-2)})
        - Ensure that similarity_score is a number
        - Validate that URLs are correct or null
        - Ensure keys are exactly as specified
        """
    

def create_competitor_details_query(lang, business_details, competitor: Dict) -> str:
    """Crea el prompt para buscar detalles específicos de un competidor"""
    competitor_name = competitor.get('competitor_name', '')
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
        4. Incluir TODAS las redes sociales disponibles
        5. Formato JSON:

        {
        "competitors": [
            {
            "competitor_name": "string", # Nombre Completo del Competidor
            "key_feature": "string", # Característica principal/clave del competidor (Propuesta de valor)
            "website": "url", # URL del sitio web
            "instagram_url": "handle", # Usuario de Instagram (si está disponible)
            "facebook_url": "handle", # Usuario de Facebook (si está disponible)
            "linkedin_url": "handle", # URL de LinkedIn (si está disponible)
            "x_url": "handle", # Usuario de Twitter/X (si está disponible)
            "youtube_url": "handle", # Canal de YouTube (si está disponible)
            "tiktok_url": "handle", # Usuario de TikTok (si está disponible)
            "similarity_score": 1-100 # Porcentaje de similitud con la idea de negocio
            }
            ]
        }

        Para cada competidor, por favor investiga y proporciona:
        - La URL exacta del sitio web verificada
        - Enlaces a TODAS las redes sociales disponibles
        - Una puntuación de similitud precisa entre 1-100

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
        3. Include ALL available social media
        4. JSON Format:
        {
            "competitors": [
                {
                "competitor_name": "string", # Competitor's Full Name
                "key_feature": "string", # Competitor's Key Feature (Value Proposition)
                "website": "url", # Competitor's Website URL
                "instagram_url": "handle", # Instagram handle (if available)
                "facebook_url": "handle", # Facebook handle (if available)
                "linkedin_url": "handle", # LinkedIn URL (if available)
                "x_url": "handle", # Twitter/X handle (if available)
                "youtube_url": "handle", # YouTube channel (if available)
                "tiktok_url": "handle", # TikTok handle (if available)
                "similarity_score": 1-100 # Similarity score with the business idea
                }
            ]
        }

        For each competitor, please research and provide:
        - The exact verified website URL
        - Links to ALL available social media
        - An accurate similarity score between 1-100

        Avoid adding extra comments in the output JSON.
        """
    
    return query

def create_analysis_prompt(lang, business_model) -> str:
    if lang == 'es':
        return f"""
        Eres un investigador doctoral (PhD) especializado en Marketing y Administración de Empresas.
        La tarea consiste en generar un conjunto de preguntas e indicaciones que guíen la
        elaboración de un "análisis de competencia".

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

# Prompt to validate using web research information of a competitor having a title, description and a posible website
def create_validation_competitor_prompt(lang, competitor_info: Dict) -> str:
    if lang == 'es':
        return f"""
        Tienes la tarea de validar/buscar la información de una empresa/startup teniendo un nombre, descripción y un posible sitio web.

        Nombre del competidor: {competitor_info['competitor_name']}

        Descripción del competidor: {competitor_info['description']}

        URL del sitio web: {competitor_info['website']}

        Usando la información de la web, valida si la información de la url del sitio web es correcta.

        Además, en base a la información de la web, busca y proporciona las URLs de las redes sociales de la empresa.

        Devuelve únicamente un JSON con la siguiente estructura:

        """ + """
        {
            "competitor_name": "string", # Competitor's Full Name
            "key_feature": "string", # Competitor's Key Feature (Value Proposition)
            "website": "url", # Competitor's Website URL
            "instagram_url": "handle", # Instagram handle (if available)
            "facebook_url": "handle", # Facebook handle (if available)
            "linkedin_url": "handle", # LinkedIn URL (if available)
            "x_url": "handle", # Twitter/X handle (if available)
            "youtube_url": "handle", # YouTube channel (if available)
            "tiktok_url": "handle", # TikTok handle (if available)
            "similarity_score": 1-100 # Similarity score with the business idea
        }
        """
    else:
        return f"""
        You have the task to validate/search the information of a company/startup having a name, description and a possible website.

        Competitor name: {competitor_info['competitor_name']}

        Competitor description: {competitor_info['description']}

        Website URL: {competitor_info['website']}

        Using the website information, validate if the website url information is correct.

        Also, based on the website information, it fetches and provides the URLs of the company's social networks.

        It returns only a JSON with the following structure:

        """ + """
        {
        "competitor_name": "string", # Competitor's Full Name
        "key_feature": "string", # Competitor's Key Feature (Value Proposition)
        "website": "url", # Competitor's Website URL
        "instagram_url": "handle", # Instagram handle (if available)
        "facebook_url": "handle", # Facebook handle (if available)
        "linkedin_url": "handle", # LinkedIn URL (if available)
        "x_url": "handle", # Twitter/X handle (if available)
        "youtube_url": "handle", # YouTube channel (if available)
        "tiktok_url": "handle", # TikTok handle (if available)
        "similarity_score": 1-100 # Similarity score with the business idea
        }
        """