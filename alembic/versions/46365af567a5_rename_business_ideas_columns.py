"""rename_business_ideas_columns

Revision ID: 46365af567a5
Revises: 8dc73e156fcf
Create Date: 2025-04-22 20:42:01.494190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '46365af567a5'
down_revision: Union[str, None] = '8dc73e156fcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Renombrar las columnas de business_ideas para que coincidan con lo que espera el modelo
    
    # Cambiar el tipo de columna nullable para user_id
    op.alter_column('business_ideas', 'user_id', 
                    existing_type=sa.String(), 
                    nullable=False)  # Cambiar nullable=True a nullable=False
    
    # Renombrar columnas
    op.alter_column('business_ideas', 'name', new_column_name='title', existing_type=sa.String())
    op.alter_column('business_ideas', 'idea', new_column_name='description', existing_type=sa.String())
    op.alter_column('business_ideas', 'value_proposition', new_column_name='value_proposal', existing_type=sa.String())
    op.alter_column('business_ideas', 'target_market', new_column_name='ideal_customer', existing_type=sa.JSON())
    op.alter_column('business_ideas', 'customer_problems', new_column_name='problem_solved', existing_type=sa.JSON())
    op.alter_column('business_ideas', 'differentiation', new_column_name='differentiators', existing_type=sa.String())
    op.alter_column('business_ideas', 'founder_skills', new_column_name='challenges_opportunities', existing_type=sa.JSON())
    
    # Cambiar tipos de columna de JSON a Text
    op.alter_column('business_ideas', 'problem_solved', 
                    type_=sa.Text(), 
                    existing_type=sa.JSON(),
                    postgresql_using="problem_solved::text")
                    
    op.alter_column('business_ideas', 'ideal_customer', 
                    type_=sa.Text(), 
                    existing_type=sa.JSON(),
                    postgresql_using="ideal_customer::text")
                    
    op.alter_column('business_ideas', 'challenges_opportunities', 
                    type_=sa.Text(), 
                    existing_type=sa.JSON(),
                    postgresql_using="challenges_opportunities::text")
                    
    op.alter_column('business_ideas', 'products_services', 
                    type_=sa.Text(), 
                    existing_type=sa.JSON(),
                    postgresql_using="products_services::text")


def downgrade() -> None:
    # Volver a los nombres y tipos originales
    
    # Revertir tipos de columna de Text a JSON
    op.alter_column('business_ideas', 'products_services', 
                    type_=sa.JSON(), 
                    existing_type=sa.Text(),
                    postgresql_using="products_services::json")
    
    op.alter_column('business_ideas', 'challenges_opportunities', 
                    type_=sa.JSON(), 
                    existing_type=sa.Text(),
                    postgresql_using="challenges_opportunities::json")
                    
    op.alter_column('business_ideas', 'ideal_customer', 
                    type_=sa.JSON(), 
                    existing_type=sa.Text(),
                    postgresql_using="ideal_customer::json")
                    
    op.alter_column('business_ideas', 'problem_solved', 
                    type_=sa.JSON(), 
                    existing_type=sa.Text(),
                    postgresql_using="problem_solved::json")
    
    # Renombrar columnas al original
    op.alter_column('business_ideas', 'challenges_opportunities', new_column_name='founder_skills', existing_type=sa.Text())
    op.alter_column('business_ideas', 'differentiators', new_column_name='differentiation', existing_type=sa.String())
    op.alter_column('business_ideas', 'problem_solved', new_column_name='customer_problems', existing_type=sa.JSON())
    op.alter_column('business_ideas', 'ideal_customer', new_column_name='target_market', existing_type=sa.JSON())
    op.alter_column('business_ideas', 'value_proposal', new_column_name='value_proposition', existing_type=sa.String())
    op.alter_column('business_ideas', 'description', new_column_name='idea', existing_type=sa.String())
    op.alter_column('business_ideas', 'title', new_column_name='name', existing_type=sa.String())
    
    # Cambiar el tipo de columna nullable para user_id de vuelta
    op.alter_column('business_ideas', 'user_id', 
                    existing_type=sa.String(), 
                    nullable=True)  # Cambiar nullable=False a nullable=True
