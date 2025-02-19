from app.services.business.business_understanding.base_business_module import BaseBusinessModule
from app.services.storage.minio_service import MinioService
from app.models.business.business_understanding.business_canvas import BusinessCanvas
import json
from datetime import datetime, UTC

BUSINESS_MODEL_TRANSLATIONS = {
    "value_proposition": {
        "en": "What is your Unique Value Proposition?",
        "es": "¿Cuál es tu Propuesta de Valor Única?"
    },
    "customer_segments": {
        "en": "Who are your customer segments?",
        "es": "¿Cuáles son tus segmentos de clientes?"
    },
    "channels": {
        "en": "What are your distribution channels?",
        "es": "¿Cuáles son tus canales de distribución?"
    },
    "customer_relationships": {
        "en": "How will you maintain customer relationships?",
        "es": "¿Cómo mantendrás las relaciones con los clientes?"
    },
    "revenue_streams": {
        "en": "What are your revenue streams?",
        "es": "¿Cuáles son tus fuentes de ingresos?"
    },
    "key_resources": {
        "en": "What key resources do you need?",
        "es": "¿Qué recursos clave necesitas?"
    },
    "key_activities": {
        "en": "What are your key activities?",
        "es": "¿Cuáles son tus actividades clave?"
    },
    "key_partners": {
        "en": "Who are your key partners?",
        "es": "¿Quiénes son tus socios clave?"
    },
    "cost_structure": {
        "en": "What is your cost structure?",
        "es": "¿Cuál es tu estructura de costos?"
    },
    "pricing_strategy": {
        "en": "What is your pricing strategy?",
        "es": "¿Cuál es tu estrategia de precios?"
    }
}

class BusinessCanvasModule(BaseBusinessModule):
    """Module for analyzing and documenting the business model"""

    def __init__(self, config, business_id: str, db):
        super().__init__(config, BUSINESS_MODEL_TRANSLATIONS)
        self.business_id = business_id
        self.db = db
        self.update_mode = False
        self.existing_canvas = None
    
    async def run(self):
        """Execute the business model analysis process"""
        await self._create_business_canvas()
        return self.results
    
    async def _create_business_canvas(self):
        """Create and analyze the business model canvas"""
        canvas_sections = [
            "customer_segments",
            "value_propositions",
            "channels",
            "customer_relationships",
            "revenue_streams",
            "key_resources",
            "key_activities",
            "key_partnerships",
            "cost_structure",
            "pricing_strategy"
        ]
        
        canvas_data = {}
        for section in canvas_sections:
            response = await self.ask_question(section)
            canvas_data[section] = response
        
        file_name = "business_canvas.json"
        json_data = json.dumps(canvas_data, indent=2)

        # Store in MinIO
        await self.store_document(
            file_name,
            json_data,
            "application/json"
        )

        file_path = f"{self.business_id}/business-understanding/{file_name}"

        if self.update_mode and self.existing_canvas:
            # Update existing record
            self.existing_canvas.file_path = file_path
            self.existing_canvas.updated_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(self.existing_canvas)
            business_canvas = self.existing_canvas
        else:
            # Create new record
            business_canvas = BusinessCanvas(
                business_idea_id=self.business_id,
                file_name=file_name,
                file_path=file_path,
                mime_type="application/json",
                bucket_name="lattice-businesses",
            )
            self.db.add(business_canvas)
            self.db.commit()
            self.db.refresh(business_canvas)
        
        self.results[self.config.language]["business_canvas"] = canvas_data
        
        return business_canvas
    
    async def store_document(self, filename: str, content: str, content_type: str):
        """Store a document in MinIO with appropriate metadata"""
        path = f"{self.business_id}/business-understanding/{filename}"
        minio_service = MinioService("lattice-businesses")
        
        await minio_service.upload_content(
            object_name=path,
            data=content,
            content_type=content_type,
            metadata={
                "business_id": self.business_id,
                "language": self.config.language,
                "document_type": filename.split('.')[0]
            }
        )