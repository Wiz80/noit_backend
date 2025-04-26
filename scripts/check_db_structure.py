import os
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

def main():
    # Cargar variables de entorno
    load_dotenv()
    
    # Crear conexión a la base de datos
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    server = os.getenv("POSTGRES_SERVER", "localhost")
    port = os.getenv("POSTGRES_PORT", "5435")
    db = os.getenv("POSTGRES_DB", "business_ai")
    
    url = f"postgresql://{user}:{password}@{server}:{port}/{db}"
    
    print(f"Conectando a: {url}")
    engine = create_engine(url)
    
    # Inspeccionar la estructura de la base de datos
    inspector = inspect(engine)
    
    print("\nColumnas en business_ideas:")
    for column in inspector.get_columns('business_ideas'):
        print(f"  - {column['name']}: {column['type']} (nullable: {column['nullable']})")
    
    print("\nVersión actual de Alembic:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        print(f"  - {result.scalar()}")

if __name__ == "__main__":
    main() 