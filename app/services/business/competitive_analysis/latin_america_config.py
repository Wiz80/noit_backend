"""
Latin America specific configuration for competitor pricing extraction.
This module contains country-specific settings, keywords, and currency formats.
"""
from typing import Dict, List, Any
from enum import Enum

class CountryConfig:
    """Configuration for specific Latin American countries"""
    
    @staticmethod
    def get_country_config(country_code: str) -> Dict[str, Any]:
        """Get country-specific configuration"""
        configs = {
            "CO": {  # Colombia
                "name": "Colombia",
                "currency": "COP",
                "currency_symbol": "$",
                "decimal_separator": ",",
                "thousands_separator": ".",
                "price_keywords": [
                    "precio", "precios", "valor", "costo", "costos", "tarifa", "tarifas",
                    "cotización", "cotizar", "vale", "cuesta"
                ],
                "product_keywords": [
                    "producto", "productos", "servicio", "servicios", "artículo", "artículos",
                    "item", "items", "mercancía", "mercadería"
                ],
                "availability_keywords": {
                    "available": ["disponible", "en stock", "hay existencias", "disponibilidad inmediata"],
                    "out_of_stock": ["agotado", "sin stock", "no disponible", "temporalmente agotado"],
                    "limited": ["pocas unidades", "últimas unidades", "stock limitado"]
                },
                "common_terms": {
                    "free": ["gratis", "gratuito", "sin costo"],
                    "discount": ["descuento", "rebaja", "oferta", "promoción"],
                    "tax": ["iva", "impuesto", "impuestos"],
                    "shipping": ["envío", "domicilio", "entrega"]
                }
            },
            "MX": {  # Mexico
                "name": "México",
                "currency": "MXN",
                "currency_symbol": "$",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "price_keywords": [
                    "precio", "precios", "costo", "costos", "importe", "monto"
                ],
                "product_keywords": [
                    "producto", "productos", "servicio", "servicios", "artículo", "mercancía"
                ],
                "availability_keywords": {
                    "available": ["disponible", "en stock", "en existencia"],
                    "out_of_stock": ["agotado", "sin existencias", "no disponible"],
                    "limited": ["pocas piezas", "últimas piezas"]
                },
                "common_terms": {
                    "free": ["gratis", "sin costo"],
                    "discount": ["descuento", "oferta"],
                    "tax": ["iva"],
                    "shipping": ["envío", "entrega"]
                }
            },
            "AR": {  # Argentina
                "name": "Argentina",
                "currency": "ARS",
                "currency_symbol": "$",
                "decimal_separator": ",",
                "thousands_separator": ".",
                "price_keywords": [
                    "precio", "precios", "valor", "importe", "costo"
                ],
                "product_keywords": [
                    "producto", "productos", "servicio", "servicios", "artículo"
                ],
                "availability_keywords": {
                    "available": ["disponible", "en stock", "hay stock"],
                    "out_of_stock": ["sin stock", "agotado", "no disponible"],
                    "limited": ["pocas unidades", "stock limitado"]
                },
                "common_terms": {
                    "free": ["gratis", "sin cargo"],
                    "discount": ["descuento", "oferta"],
                    "tax": ["iva", "impuestos"],
                    "shipping": ["envío", "entrega"]
                }
            },
            "BR": {  # Brazil
                "name": "Brasil",
                "currency": "BRL",
                "currency_symbol": "R$",
                "decimal_separator": ",",
                "thousands_separator": ".",
                "price_keywords": [
                    "preço", "preços", "valor", "custo", "custos"
                ],
                "product_keywords": [
                    "produto", "produtos", "serviço", "serviços", "item", "artigo"
                ],
                "availability_keywords": {
                    "available": ["disponível", "em estoque", "há estoque"],
                    "out_of_stock": ["esgotado", "sem estoque", "indisponível"],
                    "limited": ["poucas unidades", "estoque limitado"]
                },
                "common_terms": {
                    "free": ["grátis", "gratuito"],
                    "discount": ["desconto", "oferta", "promoção"],
                    "tax": ["imposto", "impostos"],
                    "shipping": ["frete", "entrega"]
                }
            },
            "PE": {  # Peru
                "name": "Perú",
                "currency": "PEN",
                "currency_symbol": "S/",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "price_keywords": [
                    "precio", "precios", "costo", "valor", "importe"
                ],
                "product_keywords": [
                    "producto", "productos", "servicio", "servicios", "artículo"
                ],
                "availability_keywords": {
                    "available": ["disponible", "en stock", "hay stock"],
                    "out_of_stock": ["agotado", "sin stock", "no disponible"],
                    "limited": ["pocas unidades", "stock limitado"]
                },
                "common_terms": {
                    "free": ["gratis", "gratuito"],
                    "discount": ["descuento", "oferta"],
                    "tax": ["igv", "impuesto"],
                    "shipping": ["envío", "delivery"]
                }
            },
            "CL": {  # Chile
                "name": "Chile",
                "currency": "CLP",
                "currency_symbol": "$",
                "decimal_separator": ",",
                "thousands_separator": ".",
                "price_keywords": [
                    "precio", "precios", "valor", "costo"
                ],
                "product_keywords": [
                    "producto", "productos", "servicio", "servicios"
                ],
                "availability_keywords": {
                    "available": ["disponible", "en stock"],
                    "out_of_stock": ["agotado", "sin stock"],
                    "limited": ["pocas unidades"]
                },
                "common_terms": {
                    "free": ["gratis"],
                    "discount": ["descuento", "oferta"],
                    "tax": ["iva"],
                    "shipping": ["envío", "despacho"]
                }
            }
        }
        
        # Default to Colombian config if country not found
        return configs.get(country_code, configs["CO"])

class RegionalPriceParser:
    """Parse prices according to regional formats"""
    
    @staticmethod
    def parse_regional_price(price_text: str, country_config: Dict[str, Any]) -> tuple:
        """Parse price text according to country-specific format"""
        import re
        from decimal import Decimal, InvalidOperation
        
        if not price_text:
            return None, None, False, None, None
            
        # Get separators from config
        decimal_sep = country_config["decimal_separator"]
        thousands_sep = country_config["thousands_separator"]
        currency_symbol = country_config["currency_symbol"]
        currency_code = country_config["currency"]
        
        # Clean the price text
        price_clean = price_text.strip()
        
        # Detect currency
        detected_currency = currency_code
        if currency_symbol in price_clean:
            detected_currency = currency_code
        
        # Handle different regional formats
        if country_config["currency"] == "COP":
            # Colombian format: $50.000 or $50.000.000
            pattern = r'\$?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
        elif country_config["currency"] == "MXN":
            # Mexican format: $50,000.00
            pattern = r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        elif country_config["currency"] == "BRL":
            # Brazilian format: R$ 50.000,00
            pattern = r'R\$?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
        else:
            # Default pattern
            pattern = r'[\$\w]*\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)'
        
        matches = re.findall(pattern, price_clean)
        
        if not matches:
            return None, detected_currency, False, None, None
        
        try:
            # Convert to standard decimal format
            price_str = matches[0]
            
            # Handle Colombian/Argentine format (dot as thousands, comma as decimal)
            if country_config["currency"] in ["COP", "ARS", "BRL"]:
                if ',' in price_str and price_str.split(',')[-1].isdigit() and len(price_str.split(',')[-1]) <= 2:
                    # Has decimal part
                    parts = price_str.split(',')
                    decimal_part = parts[-1]
                    integer_part = parts[0].replace('.', '')
                    clean_number = f"{integer_part}.{decimal_part}"
                else:
                    # No decimal part
                    clean_number = price_str.replace('.', '').replace(',', '')
            else:
                # Mexican/Peruvian format (comma as thousands, dot as decimal)
                clean_number = price_str.replace(',', '')
            
            price = Decimal(clean_number)
            return price, detected_currency, False, None, None
            
        except (InvalidOperation, ValueError):
            return None, detected_currency, False, None, None

# Country-specific search terms
LATIN_AMERICA_SEARCH_TERMS = {
    "pricing_urls": {
        "es": [
            "precios", "precio", "tarifas", "tarifa", "costos", "costo",
            "cotizar", "cotización", "planes", "plan", "paquetes", "paquete"
        ],
        "pt": [  # For Brazil
            "preços", "preço", "tarifas", "tarifa", "custos", "custo",
            "orçamento", "planos", "plano", "pacotes", "pacote"
        ]
    },
    "product_urls": {
        "es": [
            "productos", "producto", "servicios", "servicio", "tienda",
            "catálogo", "catalogo", "ofertas", "oferta", "comprar"
        ],
        "pt": [
            "produtos", "produto", "serviços", "serviço", "loja",
            "catálogo", "ofertas", "oferta", "comprar"
        ]
    }
}

def get_search_terms(language: str = "es") -> Dict[str, List[str]]:
    """Get search terms for the specified language"""
    return {
        "pricing": LATIN_AMERICA_SEARCH_TERMS["pricing_urls"].get(language, 
                   LATIN_AMERICA_SEARCH_TERMS["pricing_urls"]["es"]),
        "products": LATIN_AMERICA_SEARCH_TERMS["product_urls"].get(language,
                    LATIN_AMERICA_SEARCH_TERMS["product_urls"]["es"])
    } 