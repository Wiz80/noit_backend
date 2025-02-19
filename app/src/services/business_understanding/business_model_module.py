from src.core.base_module import BaseBusinessModule
import json

class BusinessModelModule(BaseBusinessModule):
    """Business Model Canvas and Monetization Module"""
    
    def __init__(self, config):
        super().__init__(config)
        self.canvas = {
            "value_proposition": {},
            "customer_segments": {},
            "channels": {},
            "customer_relationships": {},
            "revenue_streams": {},
            "key_resources": {},
            "key_activities": {},
            "key_partners": {},
            "cost_structure": {},
            "pricing_strategy": {}
        }
    
    async def run(self):
        """Execute the business model analysis"""
        await self._add_section_header()
        
        # Collect all canvas components
        for component in self.canvas.keys():
            specialized_prompt = self._get_specialized_prompt(component)
            response = await self.ask_question(
                component,
                prompt_template=specialized_prompt
            )
            self.canvas[component] = self._structure_response(response, component)
            
        # Save canvas as JSON
        await self._save_canvas()
        return self.results
    
    def _get_specialized_prompt(self, component: str) -> str:
        """Get specialized prompt for each canvas component"""
        prompts = {
            "value_proposition": {
                "en": """Analyze the value proposition considering:
                1. Main customer pain points addressed
                2. Unique benefits offered
                3. Competitive advantages
                
                Return JSON with:
                {
                    "features": ["aspect1", "aspect2", "aspect3"],
                    "suggestion": "detailed value proposition"
                }""",
                "es": """Analiza la propuesta de valor considerando:
                1. Principales dolores del cliente que se abordan
                2. Beneficios únicos ofrecidos
                3. Ventajas competitivas
                
                Devuelve JSON con:
                {
                    "features": ["aspecto1", "aspecto2", "aspecto3"],
                    "suggestion": "propuesta de valor detallada"
                }"""
            },
            # Add specialized prompts for other components...
        }
        
        return prompts.get(component, {}).get(self.config.language) or self.get_default_prompt(
            BUSINESS_MODEL_TRANSLATIONS[component][self.config.language]
        )
    
    def _structure_response(self, response: str, component: str) -> dict:
        """Structure the response for the canvas JSON"""
        return {
            "content": response,
            "category": component,
            "display_order": list(self.canvas.keys()).index(component)
        }
    
    async def _save_canvas(self):
        """Save the business model canvas as JSON"""
        output_file = f"output/business_model_canvas_{self.config.language}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.canvas, f, indent=2, ensure_ascii=False)