from services.business_understanding.business_validator_module import ValidatorConfig, BusinessValidator
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

async def main():
    business_idea = """
    Creación de marca de skin care en Colombia para hombres:
    MISION:
    Lograr tener la marca de los mejores productos de skin care/facial cleaning para hombre a nivel latinoamerica
    Ser una marca disruptiva en el mercado que utilice soluciones avanzadas de tecnología y se aplique en todos sus frentes de trabajo para ser más eficientes y brindar el mejor servicio para nuestros clientes

    Revolucionar la manera en que los hombres descubren y acceden al cuidado de la piel, combinando un portafolio de productos de calidad con estrategias digitales innovadoras. A través de una comunicación disruptiva y el uso inteligente de tecnología, queremos derribar estigmas y empoderar a cada hombre en su camino hacia una mejor salud facial.
    
    VISIÓN:
    Convertirnos en la principal referencia de skincare masculino en Latinoamérica, reconocidos por nuestro enfoque estratégico y creativo en marketing y ventas, impulsado por tecnología disruptiva. Deseamos liderar la transformación cultural en torno al cuidado de la piel para hombres, siendo la plataforma más confiable y aspiracional para quienes buscan soluciones efectivas y una experiencia de marca única.
    """
    config = ValidatorConfig(
        business_idea=business_idea,
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
        validator_provider="openai",
        validator_model="openai:gpt-4o",
        language="es"
    )
    validator = BusinessValidator(config)
    await validator.run()  # Añadir await

if __name__ == "__main__":
    asyncio.run(main())