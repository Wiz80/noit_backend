import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, inspect
from sqlalchemy.ext.declarative import declarative_base
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

# Agrega la ruta del proyecto al sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    # Cargar variables de entorno
    load_dotenv()
    
    # Crear configuración de Alembic
    alembic_cfg = Config("alembic.ini")
    
    # Crear la migración
    message = "rename_business_ideas_columns"
    command.revision(alembic_cfg, autogenerate=False, message=message)
    
    print(f"Creada una nueva migración con el mensaje: {message}")
    print("Ahora edita el archivo de migración en alembic/versions/ para agregar las operaciones de renombrado de columnas")

if __name__ == "__main__":
    main() 