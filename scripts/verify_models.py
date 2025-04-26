from sqlalchemy import inspect
from app.db.session import engine
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel

# Create inspector
inspector = inspect(engine)

# Check BusinessIdea columns
print("BusinessIdea columns:")
for column in inspector.get_columns("business_ideas"):
    print(f"  - {column['name']} ({column['type']})")

# Check BusinessModel columns
print("\nBusinessModel columns:")
for column in inspector.get_columns("business_models"):
    print(f"  - {column['name']} ({column['type']})") 