"""
Brief Suggestions Utilities
Pre-defined generic suggestions for each brief question to improve performance
"""
from typing import Dict, Optional

# Sugerencias genéricas para cada pregunta del brief
BRIEF_SUGGESTIONS = {
    # ETAPA 1: ENTENDIMIENTO DEL NEGOCIO
    "¿Qué hace la empresa? ¿Cuál es su propósito?": """
💡 Cómo responder efectivamente:

Para responder a "¿Qué hace la empresa? ¿Cuál es su propósito?", incluye:

1. **Actividad principal**: ¿A qué se dedica específicamente tu empresa?
2. **Propósito/Misión**: ¿Por qué existe tu empresa? ¿Qué busca lograr?
3. **Sector/Industria**: ¿En qué mercado opera?
4. **Alcance**: ¿Es local, nacional, internacional?

**Ejemplo**: "Somos una plataforma de educación online que se dedica a enseñar marketing digital a profesionales latinoamericanos. Nuestro propósito es democratizar el acceso a educación de calidad en marketing digital para impulsar el crecimiento profesional en la región."
""",

    "¿Cuál es su propuesta de valor?": """
💡 Cómo responder efectivamente:

Para explicar tu propuesta de valor, considera:

1. **Problema que resuelves**: ¿Qué necesidad específica atiendes?
2. **Solución única**: ¿Cómo lo resuelves de manera diferente?
3. **Beneficios concretos**: ¿Qué obtienen tus clientes?
4. **Diferenciador clave**: ¿Por qué elegirte sobre otras opciones?

**Estructura recomendada**: "Ayudamos a [cliente ideal] a [resultado específico] mediante [método único], lo que les permite [beneficio final]."

**Ejemplo**: "Ofrecemos la educación en marketing digital más práctica y actualizada de Latinoamérica, con casos reales de la región y mentores certificados, permitiendo a profesionales incrementar sus ingresos en promedio 40% en 6 meses."
""",

    "¿Qué productos/servicios ofrece y a quiénes?": """
💡 Cómo responder efectivamente:

Describe claramente:

1. **Productos/Servicios específicos**: Lista concreta de lo que ofreces
2. **Público objetivo**: ¿Quiénes son tus clientes ideales?
3. **Segmentación**: ¿Tienes diferentes ofertas para diferentes grupos?
4. **Modalidades**: ¿Cómo se entregan tus productos/servicios?

**Ejemplo**: "Ofrecemos cursos online de marketing digital en tres niveles: básico, intermedio y avanzado. También brindamos mentoría personalizada y certificaciones. Dirigido a profesionales de 25-45 años, emprendedores y equipos de marketing de PYMES en Latinoamérica."
""",

    "¿Cuál es el cliente ideal?": """
💡 Cómo responder efectivamente:

Define a tu cliente ideal considerando:

1. **Demografía**: Edad, ubicación, nivel socioeconómico
2. **Psicografía**: Intereses, valores, estilo de vida
3. **Comportamiento**: Hábitos de compra, uso de tecnología
4. **Necesidades**: Problemas específicos que busca resolver
5. **Capacidad**: Presupuesto y poder de decisión

**Ejemplo**: "Nuestro cliente ideal es un profesional de marketing de 28-40 años, ubicado en ciudades principales de LATAM, con 3-8 años de experiencia, que busca especializarse en marketing digital para avanzar en su carrera y aumentar sus ingresos. Valora el aprendizaje práctico y tiene presupuesto para invertir en su desarrollo profesional."
""",

    "¿Qué problema resuelve?": """
💡 Cómo responder efectivamente:

Explica el problema que resuelves:

1. **Problema específico**: ¿Qué dolor o necesidad atiendes?
2. **Magnitud**: ¿Qué tan común o grave es este problema?
3. **Consecuencias**: ¿Qué pasa si no se resuelve?
4. **Contexto**: ¿Por qué existe este problema?

**Ejemplo**: "Resolvemos la falta de educación práctica y actualizada en marketing digital en Latinoamérica. Muchos profesionales estudian teoría desactualizada que no aplica a la realidad regional, limitando su crecimiento profesional y capacidad de generar resultados reales para sus empresas."
""",

    "¿Qué los hace diferentes frente a la competencia?": """
💡 Cómo responder efectivamente:

Identifica tus diferenciadores:

1. **Ventajas únicas**: ¿Qué tienes que otros no?
2. **Fortalezas clave**: ¿En qué eres especialmente bueno?
3. **Enfoque distintivo**: ¿Cómo abordas el problema de manera diferente?
4. **Valor agregado**: ¿Qué extra ofreces?

**Ejemplo**: "Nos diferenciamos por ser 100% enfocados en Latinoamérica, con casos de estudio reales de la región, mentores que han trabajado en las principales empresas latinas, y contenido actualizado mensualmente basado en las últimas tendencias del mercado regional."
""",

    "¿Qué desafíos u oportunidades clave enfrentan hoy?": """
💡 Cómo responder efectivamente:

Analiza tu situación actual:

1. **Desafíos principales**: ¿Qué obstáculos enfrentas?
2. **Oportunidades del mercado**: ¿Qué tendencias puedes aprovechar?
3. **Recursos**: ¿Qué necesitas para crecer?
4. **Timing**: ¿Qué es urgente vs. importante?

**Ejemplo**: "Nuestro principal desafío es la competencia de plataformas internacionales con mayor presupuesto de marketing. Sin embargo, vemos una gran oportunidad en el crecimiento del e-commerce en LATAM post-pandemia y la necesidad creciente de profesionales especializados en marketing digital regional."
""",

    "¿En qué industria se encuentra?": """
💡 Cómo responder efectivamente:

Define tu industria claramente:

1. **Sector principal**: ¿Cuál es tu industria primaria?
2. **Subsector**: ¿Hay una especialización específica?
3. **Ecosistema**: ¿Con qué otras industrias te relacionas?
4. **Tendencias**: ¿Cómo está evolucionando tu industria?

**Ejemplo**: "Operamos en la industria de educación online, específicamente en el subsector de capacitación profesional en marketing digital. Nos relacionamos estrechamente con las industrias de tecnología, publicidad y recursos humanos."
""",

    # ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN
    "¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?": """
💡 Cómo responder efectivamente:

Analiza el contexto que motiva la comunicación:

1. **Cambios del mercado**: ¿Qué está cambiando en tu industria?
2. **Comportamiento del consumidor**: ¿Cómo están evolucionando las preferencias?
3. **Competencia**: ¿Qué están haciendo otros players?
4. **Oportunidades**: ¿Qué ventanas se están abriendo?

**Ejemplo**: "El mercado de educación online creció 300% post-pandemia, pero muchas plataformas no ofrecen contenido regionalizado. Los profesionales latinoamericanos buscan cada vez más capacitación específica para su mercado."
""",

    "¿Cuál es la oportunidad de negocio concreta?": """
💡 Cómo responder efectivamente:

Define la oportunidad específica:

1. **Mercado objetivo**: ¿Qué segmento específico puedes capturar?
2. **Tamaño de la oportunidad**: ¿Cuál es el potencial?
3. **Timing**: ¿Por qué es el momento correcto?
4. **Recursos necesarios**: ¿Qué se requiere para aprovecharla?

**Ejemplo**: "Existe una oportunidad de capturar el 15% del mercado de capacitación en marketing digital en México y Colombia, valorado en $50M USD, aprovechando la carencia de contenido localizado y la creciente demanda post-pandemia."
""",

    "¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?": """
💡 Cómo responder efectivamente:

Define claramente el objetivo:

1. **Objetivo principal**: ¿Cuál es la meta principal?
2. **Objetivos secundarios**: ¿Qué otros resultados buscas?
3. **Métricas**: ¿Cómo medirás el éxito?
4. **Plazo**: ¿En qué tiempo esperas resultados?

**Opciones comunes**: Awareness, Posicionamiento, Lanzamiento, Conversión, Retención, Diferenciación

**Ejemplo**: "El objetivo principal es posicionamiento como la plataforma líder en educación de marketing digital para LATAM, aumentando awareness del 12% al 35% en 6 meses y generando 500 nuevos estudiantes mensuales."
""",

    # ETAPA 3: ESTRATEGIA DE COMUNICACIÓN
    "¿Cuál es la idea o mensaje clave a comunicar?": """
💡 Cómo responder efectivamente:

Define tu mensaje central:

1. **Idea principal**: ¿Cuál es el concepto central?
2. **Mensaje único**: ¿Qué quieres que recuerden?
3. **Tono**: ¿Cómo quieres sonar?
4. **Call to action**: ¿Qué acción esperas?

**Ejemplo**: "El mensaje clave es 'Transforma tu carrera con la educación en marketing digital más práctica de Latinoamérica'. Queremos comunicar que ofrecemos resultados reales con casos y mentores regionales."
""",

    "¿A quién va dirigida esta comunicación?": """
💡 Cómo responder efectivamente:

Define tu audiencia específica:

1. **Segmento primario**: ¿Quién es tu audiencia principal?
2. **Segmentos secundarios**: ¿Hay otros grupos relevantes?
3. **Características**: ¿Cómo son demográfica y psicográficamente?
4. **Comportamiento mediático**: ¿Dónde consumen información?

**Ejemplo**: "Audiencia primaria: profesionales de marketing de 25-35 años en México, Colombia y Chile, activos en LinkedIn e Instagram, que buscan avanzar en sus carreras y aumentar ingresos."
""",

    "¿Qué valores o características tiene esta audiencia que deberíamos considerar?": """
💡 Cómo responder efectivamente:

Analiza los valores de tu audiencia:

1. **Valores centrales**: ¿Qué es importante para ellos?
2. **Motivaciones**: ¿Qué los impulsa?
3. **Miedos/Preocupaciones**: ¿Qué los detiene?
4. **Aspiraciones**: ¿Qué buscan lograr?

**Ejemplo**: "Valoran el crecimiento profesional, la estabilidad económica y el reconocimiento. Son ambiciosos pero cautelosos con las inversiones. Priorizan el aprendizaje práctico sobre la teoría."
""",

    "¿Por qué nos creerían?": """
💡 Cómo responder efectivamente:

Establece tu credibilidad:

1. **Pruebas sociales**: ¿Qué testimonios o casos tienes?
2. **Experiencia**: ¿Qué track record demuestras?
3. **Autoridad**: ¿Qué te da legitimidad?
4. **Garantías**: ¿Qué respaldo ofreces?

**Ejemplo**: "Tenemos +3000 egresados con incrementos promedio del 40% en sus ingresos, mentores que han trabajado en Google y Facebook, y casos de éxito documentados en empresas como Mercado Libre y Rappi."
""",

    "¿Qué hace nuestra promesa creíble?": """
💡 Cómo responder efectivamente:

Refuerza la credibilidad de tu promesa:

1. **Evidencia concreta**: ¿Qué datos la respaldan?
2. **Metodología**: ¿Cómo garantizas los resultados?
3. **Transparencia**: ¿Qué muestras del proceso?
4. **Garantías**: ¿Qué aseguras?

**Ejemplo**: "Nuestra promesa es creíble porque el 87% de nuestros graduados obtiene promociones o nuevos empleos en 6 meses, seguimos una metodología basada en proyectos reales, y ofrecemos garantía de satisfacción 100%."
""",

    "¿Cómo vamos a sonar (tono, voz, estilo)?": """
💡 Cómo responder efectivamente:

Define tu personalidad de marca:

1. **Tono**: ¿Formal, casual, amigable, profesional?
2. **Personalidad**: ¿Qué adjetivos te describen?
3. **Estilo**: ¿Cómo te expresas?
4. **Consistencia**: ¿Cómo mantienes coherencia?

**Ejemplo**: "Tono profesional pero cercano, inspirador y práctico. Personalidad: experta, motivadora, regional, auténtica. Estilo directo con ejemplos reales y lenguaje claro sin tecnicismos innecesarios."
""",

    "¿Cuál es el indicador de éxito más importante?": """
💡 Cómo responder efectivamente:

Define tu métrica principal:

1. **KPI principal**: ¿Cuál es la métrica más importante?
2. **KPIs secundarios**: ¿Qué otros indicadores importan?
3. **Medición**: ¿Cómo vas a trackear?
4. **Frecuencia**: ¿Con qué periodicidad evaluarás?

**Ejemplo**: "El indicador principal es el número de nuevas inscripciones mensuales (meta: 500/mes). Secundarios: awareness en surveys (35%), engagement en redes sociales (+200%), y costo de adquisición (<$50 USD)."
""",

    "¿Qué cifras o resultados esperamos?": """
💡 Cómo responder efectivamente:

Establece expectativas cuantificables:

1. **Objetivos numéricos**: ¿Qué cifras concretas buscas?
2. **Plazos**: ¿En qué tiempo esperas lograrlos?
3. **Baseline**: ¿Cuál es tu punto de partida?
4. **Realismo**: ¿Son objetivos alcanzables?

**Ejemplo**: "Esperamos 500 nuevas inscripciones mensuales (+150% vs. actual), 35% de awareness en mercados target (+180% vs. actual), y ROI de 300% en los primeros 12 meses de la campaña."
""",

    "¿Qué queremos que la audiencia piense, sienta o haga después de recibir esta comunicación?": """
💡 Cómo responder efectivamente:

Define el resultado esperado:

1. **Pensar**: ¿Qué percepción quieres generar?
2. **Sentir**: ¿Qué emociones buscas despertar?
3. **Hacer**: ¿Qué acción específica esperas?
4. **Secuencia**: ¿Cuál es el journey esperado?

**Ejemplo**: "Queremos que piensen 'Esta es la mejor opción para avanzar en marketing digital en LATAM', que sientan confianza y motivación, y que se inscriban al curso introductorio gratuito como primer paso."
""",

    "¿Hay limitaciones legales, presupuestarias o de formatos?": """
💡 Cómo responder efectivamente:

Identifica las restricciones:

1. **Limitaciones legales**: ¿Qué no puedes decir o hacer?
2. **Presupuesto**: ¿Cuáles son los límites financieros?
3. **Formatos**: ¿Hay restricciones de medios o formatos?
4. **Tiempo**: ¿Hay deadlines específicos?

**Ejemplo**: "Presupuesto limitado a $50K USD/mes, no podemos hacer promesas específicas de aumento salarial por regulaciones, debemos incluir disclaimers sobre resultados, y priorizamos formatos digitales sobre tradicionales."
""",

    "¿Canales obligatorios o a evitar?": """
💡 Cómo responder efectivamente:

Define tus canales de comunicación:

1. **Obligatorios**: ¿Qué canales DEBES usar?
2. **Prohibidos**: ¿Cuáles DEBES evitar?
3. **Recomendados**: ¿Cuáles son ideales para tu audiencia?
4. **Recursos**: ¿Qué canales puedes manejar bien?

**Ejemplo**: "Obligatorios: LinkedIn e Instagram (donde está nuestra audiencia). A evitar: TikTok (no es profesional) y radio tradicional (baja efectividad). Recomendados: YouTube, email marketing y webinars."
""",

    "¿Fechas clave?": """
💡 Cómo responder efectivamente:

Establece tu cronograma:

1. **Fechas críticas**: ¿Cuándo es indispensable estar listos?
2. **Estacionalidad**: ¿Hay períodos más efectivos?
3. **Eventos relevantes**: ¿Hay fechas que aprovechar?
4. **Deadlines**: ¿Cuáles son los plazos firmes?

**Ejemplo**: "Lanzamiento: enero 2024 (aprovechando propósitos de año nuevo). Inscripciones abiertas: febrero-marzo (pico de interés en capacitación). Black Friday educativo: noviembre. Deadlines creativos: 15 diciembre."
"""
}

def get_suggestion_answer(question: str) -> str:
    """
    Get a pre-defined generic suggestion for how to answer a specific brief question
    
    Args:
        question: The brief question
        
    Returns:
        Generic suggestion text for answering the question
    """
    return BRIEF_SUGGESTIONS.get(question, "Piensa en los aspectos más importantes de esta pregunta para tu negocio.")

def get_all_suggestions() -> Dict[str, str]:
    """
    Get all pre-defined suggestions
    
    Returns:
        Dictionary with all questions and their corresponding suggestions
    """
    return BRIEF_SUGGESTIONS.copy()

def get_suggestions_by_phase() -> Dict[str, Dict[str, str]]:
    """
    Get suggestions organized by phase
    
    Returns:
        Dictionary organized by phases
    """
    phases = {
        "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO": [
            "¿Qué hace la empresa? ¿Cuál es su propósito?",
            "¿Cuál es su propuesta de valor?",
            "¿Qué productos/servicios ofrece y a quiénes?",
            "¿Cuál es el cliente ideal?",
            "¿Qué problema resuelve?",
            "¿Qué los hace diferentes frente a la competencia?",
            "¿Qué desafíos u oportunidades clave enfrentan hoy?",
            "¿En qué industria se encuentra?"
        ],
        "ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN": [
            "¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?",
            "¿Cuál es la oportunidad de negocio concreta?",
            "¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?"
        ],
        "ETAPA 3: ESTRATEGIA DE COMUNICACIÓN": [
            "¿Cuál es la idea o mensaje clave a comunicar?",
            "¿A quién va dirigida esta comunicación?",
            "¿Qué valores o características tiene esta audiencia que deberíamos considerar?",
            "¿Por qué nos creerían?",
            "¿Qué hace nuestra promesa creíble?",
            "¿Cómo vamos a sonar (tono, voz, estilo)?",
            "¿Cuál es el indicador de éxito más importante?",
            "¿Qué cifras o resultados esperamos?",
            "¿Qué queremos que la audiencia piense, sienta o haga después de recibir esta comunicación?",
            "¿Hay limitaciones legales, presupuestarias o de formatos?",
            "¿Canales obligatorios o a evitar?",
            "¿Fechas clave?"
        ]
    }
    
    result = {}
    for phase, questions in phases.items():
        result[phase] = {}
        for question in questions:
            result[phase][question] = get_suggestion_answer(question)
    
    return result 