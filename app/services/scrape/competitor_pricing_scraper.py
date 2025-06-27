import os
import json
import logging
import concurrent.futures
import re
from decimal import Decimal, InvalidOperation
from functools import partial
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
from pydantic import BaseModel, Field

# Import ScrapeGraphAI components
from scrapegraphai.graphs import SmartScraperGraph
from playwright.async_api import Error as PlaywrightError, async_playwright
import asyncio

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductInfo(BaseModel):
    """Schema for product information"""
    name: str = Field(description="Product or service name")
    price: Optional[str] = Field(description="Price as displayed (with currency symbol)")
    description: Optional[str] = Field(description="Product description")
    product_url: Optional[str] = Field(description="Direct URL to the product page")
    image_urls: Optional[List[str]] = Field(description="List of product image URLs")
    features: Optional[List[str]] = Field(description="List of product features")
    category: Optional[str] = Field(description="Product category")
    availability: Optional[str] = Field(description="Product availability status")

class PricingPageInfo(BaseModel):
    """Schema for pricing page information"""
    pricing_urls: List[str] = Field(description="URLs where pricing information is found")
    products_urls: List[str] = Field(description="URLs where products/services are listed")

class CompetitorPricingScraper:
    """
    Service for extracting pricing information from competitor websites using ScrapeGraphAI.
    This service uses AI-powered scraping to find pricing pages and extract product/service information.
    """

    def __init__(
        self, 
        llm_provider: str = "openai", 
        llm_model: str = "gpt-4o-mini", 
        api_key: Optional[str] = None,
        headless: bool = True,
        verbose: bool = False
    ):
        """
        Initialize the CompetitorPricingScraper.
        
        Args:
            llm_provider: The LLM provider to use ('openai', 'ollama', etc.)
            llm_model: The model to use for extraction
            api_key: API key for the LLM provider (if needed)
            headless: Whether to run browser in headless mode
            verbose: Whether to output detailed logs
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key or os.environ.get(f"{llm_provider.upper()}_API_KEY")
        self.headless = headless
        self.verbose = verbose

    def _get_graph_config(self) -> Dict[str, Any]:
        """
        Get the configuration for the ScrapeGraphAI graph.
        
        Returns:
            Dict with configuration settings for the ScrapeGraphAI graph
        """
        config = {
            "llm": {
                "model": f"{self.llm_provider}/{self.llm_model}" if self.llm_provider != "openai" else self.llm_model,
            },
            "verbose": self.verbose,
            "headless": self.headless
        }
        
        # Add API key if provided
        if self.api_key and self.llm_provider in ["openai", "anthropic", "mistral", "groq"]:
            config["llm"]["api_key"] = self.api_key
            
        return config

    def _create_pricing_urls_prompt(self) -> str:
        """
        Create the prompt for finding pricing URLs.
        
        Returns:
            String prompt that tells the AI what URLs to find
        """
        return """
        Analiza este sitio web y encuentra todas las URLs relacionadas con:
        1. Páginas de precios (precios, pricing, planes, costos, tarifas, cotizaciones)
        2. Páginas de productos (productos, servicios, tienda, shop, catálogo)
        3. Páginas de servicios (servicios, ofertas, soluciones)
        
        Busca en menús de navegación, enlaces y botones que lleven a:
        - Información de precios y tarifas
        - Catálogos de productos
        - Listados de servicios
        - Páginas de compras/tienda
        - Planes y paquetes
        
        También busca términos en español como:
        - "precios", "precio", "tarifas", "costos", "cotizar"
        - "productos", "servicios", "catálogo", "tienda"
        - "planes", "paquetes", "ofertas"
        
        Devuelve los resultados como un objeto JSON con:
        - pricing_urls: lista de URLs que contienen información de precios
        - products_urls: lista de URLs que contienen listados de productos/servicios
        
        Incluye URLs tanto relativas como absolutas. Si son relativas, incluye el dominio base.
        """

    def _create_products_extraction_prompt(self) -> str:
        """
        Create the prompt for extracting product information.
        
        Returns:
            String prompt that tells the AI what product information to extract
        """
        return """
        Extrae información detallada de productos y servicios de esta página.
        Busca todos los productos, servicios o planes listados con sus precios.
        
        Para cada producto/servicio, extrae:
        1. Nombre del producto/servicio
        2. Precio (incluye símbolo de moneda y texto exacto como se muestra)
        3. Descripción o resumen breve
        4. URL directa a la página del producto (si está disponible)
        5. URLs de imágenes (fotos de productos, logos, etc.)
        6. Características o beneficios listados
        7. Categoría o tipo de producto/servicio
        8. Estado de disponibilidad (en stock, disponible, etc.)
        
        Busca precios en formato colombiano y latinoamericano:
        - Pesos colombianos: $50.000, $50,000, COP 50000
        - Dólares: US$100, USD 100, $100 USD
        - Otros formatos locales con punto o coma como separador de miles
        
        Busca términos como:
        - "precio", "costo", "valor", "tarifa"
        - "disponible", "en stock", "agotado"
        - "características", "beneficios", "incluye"
        
        Devuelve los resultados como una lista de productos, donde cada producto tiene estos campos:
        - name: nombre del producto/servicio
        - price: precio como se muestra con moneda
        - description: descripción del producto
        - product_url: URL directa a la página del producto
        - image_urls: lista de URLs de imágenes
        - features: lista de características/beneficios
        - category: categoría del producto
        - availability: estado de disponibilidad
        
        Si no se encuentran productos, devuelve una lista vacía.
        """

    def _normalize_url(self, url: str, base_url: str = "") -> str:
        """
        Normalize a URL by ensuring it has a proper scheme and is absolute.
        
        Args:
            url: The URL to normalize
            base_url: Base URL to use for relative URLs
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
            
        # If it's already absolute, return as is
        if urlparse(url).scheme:
            return url
            
        # If it's relative and we have a base URL, join them
        if base_url:
            return urljoin(base_url, url)
            
        # Add https:// if no scheme is provided
        if not urlparse(url).scheme:
            return f"https://{url}"
        return url

    def _parse_price(self, price_text: str) -> Tuple[Optional[Decimal], Optional[str], bool, Optional[Decimal], Optional[Decimal]]:
        """
        Parse price text to extract price, currency, and determine if it's a range.
        
        Args:
            price_text: Raw price text
            
        Returns:
            Tuple of (price, currency, is_range, min_price, max_price)
        """
        if not price_text:
            return None, None, False, None, None
            
        # Extended currency patterns for Latin America
        currency_patterns = {
            # Symbols - Latin America focus
            '$': 'COP',   # Default to COP for Colombian market
            '€': 'EUR', 
            '£': 'GBP', 
            '¥': 'JPY',
            'R$': 'BRL',  # Brazilian Real
            'S/': 'PEN',  # Peruvian Sol
            'Q': 'GTQ',   # Guatemalan Quetzal
            '₡': 'CRC',   # Costa Rican Colón
            
            # Currency codes - Latin America priority
            'COP': 'COP',  # Colombian Peso
            'MXN': 'MXN',  # Mexican Peso
            'ARS': 'ARS',  # Argentine Peso
            'BRL': 'BRL',  # Brazilian Real
            'PEN': 'PEN',  # Peruvian Sol
            'CLP': 'CLP',  # Chilean Peso
            'VES': 'VES',  # Venezuelan Bolívar
            'BOB': 'BOB',  # Bolivian Boliviano
            'PYG': 'PYG',  # Paraguayan Guaraní
            'UYU': 'UYU',  # Uruguayan Peso
            'GTQ': 'GTQ',  # Guatemalan Quetzal
            'CRC': 'CRC',  # Costa Rican Colón
            'PAB': 'PAB',  # Panamanian Balboa
            'HNL': 'HNL',  # Honduran Lempira
            'NIO': 'NIO',  # Nicaraguan Córdoba
            'SVC': 'SVC',  # Salvadoran Colón
            'DOP': 'DOP',  # Dominican Peso
            
            # International currencies
            'USD': 'USD',  
            'EUR': 'EUR', 
            'GBP': 'GBP', 
            'JPY': 'JPY',
            
            # Spanish terms
            'PESOS': 'COP',
            'PESO': 'COP',
            'DOLARES': 'USD',
            'DÓLARES': 'USD',
            'EUROS': 'EUR'
        }
        
        # Extract currency
        currency = None
        for symbol, code in currency_patterns.items():
            if symbol in price_text:
                currency = code
                break
        
        # Extract numbers from price text - handle Latin American formats
        # Handle both comma and period as decimal separators
        # Colombian format: $50.000 or $50,000 (thousands), $50.000,50 (with decimals)
        # Also handle: $50.000.000 (millions)
        
        # First, identify if we have Colombian-style thousands separators
        price_clean = price_text.upper()
        
        # Look for patterns like $50.000 or $50,000 or $50.000.000
        if re.search(r'\$\s*\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?', price_clean):
            # Colombian/Latin format with thousands separators
            number_pattern = r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?'
            numbers_raw = re.findall(number_pattern, price_text)
            numbers = []
            for num in numbers_raw:
                # Convert Colombian format to standard decimal
                # If it ends with 2 digits after last separator, treat as decimal
                if re.match(r'.*[.,]\d{2}$', num):
                    # Has decimal part
                    parts = re.split(r'[.,]', num)
                    decimal_part = parts[-1]
                    integer_parts = parts[:-1]
                    clean_integer = ''.join(integer_parts)
                    clean_number = f"{clean_integer}.{decimal_part}"
                else:
                    # No decimal part, remove all separators
                    clean_number = re.sub(r'[.,]', '', num)
                
                try:
                    numbers.append(clean_number)
                except:
                    continue
        else:
            # Standard format
            number_pattern = r'\d+(?:[.,]\d+)?'
            numbers = re.findall(number_pattern, price_text.replace(',', ''))
        
        if not numbers:
            return None, currency, False, None, None
            
        try:
            # Convert to Decimal
            prices = [Decimal(num) for num in numbers]
            
            # Determine if it's a range
            if len(prices) >= 2:
                min_price = min(prices)
                max_price = max(prices)
                return (min_price + max_price) / 2, currency, True, min_price, max_price
            else:
                price = prices[0]
                return price, currency, False, None, None
                
        except InvalidOperation:
            return None, currency, False, None, None

    async def find_pricing_urls(self, website_url: str) -> Dict[str, List[str]]:
        """
        Find URLs that contain pricing and product information.
        
        Args:
            website_url: The URL of the website to analyze
            
        Returns:
            Dictionary containing lists of pricing and product URLs
        """
        try:
            # Normalize URL
            normalized_url = self._normalize_url(website_url)
            if not normalized_url:
                logger.error(f"Invalid website URL: {website_url}")
                return {"pricing_urls": [], "products_urls": []}
                
            logger.info(f"Finding pricing URLs for: {normalized_url}")
            
            # Try custom extraction first
            try:
                result = await self._custom_find_pricing_urls(normalized_url)
                if result and (result.get("pricing_urls") or result.get("products_urls")):
                    return result
                else:
                    # Fallback to SmartScraperGraph
                    logger.info(f"Custom URL finding failed, using SmartScraperGraph for {normalized_url}")
                    return await self._smart_scraper_find_urls(normalized_url)
                    
            except Exception as e:
                logger.error(f"Error finding pricing URLs for {normalized_url}: {str(e)}")
                return {"pricing_urls": [], "products_urls": []}
                
        except Exception as e:
            logger.error(f"Unexpected error in find_pricing_urls: {str(e)}")
            return {"pricing_urls": [], "products_urls": []}

    async def _custom_find_pricing_urls(self, url: str) -> Dict[str, List[str]]:
        """
        Custom implementation to find pricing URLs using Playwright directly.
        
        Args:
            url: Website URL to analyze
            
        Returns:
            Dictionary with pricing and product URLs
        """
        result = {"pricing_urls": [], "products_urls": []}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    ),
                    ignore_https_errors=True
                )
                page = await context.new_page()
                page.set_default_timeout(60000)
                
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                
                # Find pricing-related links - Latin America focus
                pricing_keywords = [
                    # Spanish terms
                    'precios', 'precio', 'tarifa', 'tarifas', 'costo', 'costos', 
                    'cotizar', 'cotizacion', 'cotización', 'plan', 'planes', 
                    'paquete', 'paquetes', 'suscripcion', 'suscripción',
                    # English terms (still common)
                    'pricing', 'price', 'cost', 'rate', 'fee', 'subscription', 'package'
                ]
                product_keywords = [
                    # Spanish terms
                    'productos', 'producto', 'servicios', 'servicio', 'tienda', 
                    'catalogo', 'catálogo', 'ofertas', 'oferta', 'soluciones', 
                    'solucion', 'solución', 'comprar',
                    # English terms (still common)
                    'product', 'service', 'shop', 'store', 'catalog', 'offering', 'solution'
                ]
                
                # Get all links
                links = await page.query_selector_all('a[href]')
                
                for link in links:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    
                    if href and text:
                        href = self._normalize_url(href, url)
                        text_lower = text.lower()
                        href_lower = href.lower()
                        
                        # Check for pricing URLs
                        if any(keyword in text_lower or keyword in href_lower for keyword in pricing_keywords):
                            if href not in result["pricing_urls"]:
                                result["pricing_urls"].append(href)
                        
                        # Check for product URLs
                        if any(keyword in text_lower or keyword in href_lower for keyword in product_keywords):
                            if href not in result["products_urls"]:
                                result["products_urls"].append(href)
                
                await browser.close()
                return result
                
        except Exception as e:
            logger.error(f"Error in custom pricing URL extraction: {str(e)}")
            return result

    async def _smart_scraper_find_urls(self, url: str) -> Dict[str, List[str]]:
        """
        Use SmartScraperGraph to find pricing URLs.
        
        Args:
            url: Website URL to analyze
            
        Returns:
            Dictionary with pricing and product URLs
        """
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor, 
                    self._run_smart_scraper_urls_in_thread, 
                    url
                )
                
                if result and isinstance(result, dict):
                    return {
                        "pricing_urls": result.get("pricing_urls", []),
                        "products_urls": result.get("products_urls", [])
                    }
                else:
                    return {"pricing_urls": [], "products_urls": []}
                    
        except Exception as e:
            logger.error(f"Error in SmartScraperGraph URL finding: {str(e)}")
            return {"pricing_urls": [], "products_urls": []}

    def _run_smart_scraper_urls_in_thread(self, url: str) -> Dict[str, Any]:
        """
        Run SmartScraperGraph in a separate thread to find URLs.
        
        Args:
            url: Website URL to analyze
            
        Returns:
            Raw extraction results from SmartScraperGraph
        """
        try:
            graph_config = self._get_graph_config()
            graph_config["browser"] = {"sync": True}
            
            smart_scraper = SmartScraperGraph(
                prompt=self._create_pricing_urls_prompt(),
                source=url,
                config=graph_config
            )
            
            return smart_scraper.run()
            
        except Exception as e:
            logger.error(f"Error in _run_smart_scraper_urls_in_thread: {str(e)}")
            return {}

    async def extract_products_from_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Extract product information from a specific URL.
        
        Args:
            url: URL to extract products from
            
        Returns:
            List of product information dictionaries
        """
        try:
            normalized_url = self._normalize_url(url)
            logger.info(f"Extracting products from: {normalized_url}")
            
            # Try custom extraction first
            try:
                products = await self._custom_extract_products(normalized_url)
                if products:
                    return products
                else:
                    # Fallback to SmartScraperGraph
                    logger.info(f"Custom product extraction failed, using SmartScraperGraph for {normalized_url}")
                    return await self._smart_scraper_extract_products(normalized_url)
                    
            except Exception as e:
                logger.error(f"Error extracting products from {normalized_url}: {str(e)}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error in extract_products_from_url: {str(e)}")
            return []

    async def _custom_extract_products(self, url: str) -> List[Dict[str, Any]]:
        """
        Custom implementation to extract products using Playwright directly.
        
        Args:
            url: URL to extract products from
            
        Returns:
            List of product information
        """
        products = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/123.0.0.0 Safari/537.36"
                    ),
                    ignore_https_errors=True
                )
                page = await context.new_page()
                page.set_default_timeout(60000)
                
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                
                # Look for common product/pricing patterns
                selectors = [
                    '.product', '.service', '.plan', '.package', '.pricing-card',
                    '[class*="product"]', '[class*="service"]', '[class*="price"]',
                    '[class*="plan"]', '[class*="package"]'
                ]
                
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        
                        for element in elements:
                            try:
                                # Extract product information
                                name_elem = await element.query_selector('h1, h2, h3, h4, .title, .name, [class*="title"], [class*="name"]')
                                price_elem = await element.query_selector('.price, [class*="price"], [class*="cost"], .amount')
                                desc_elem = await element.query_selector('.description, .desc, p, [class*="description"]')
                                img_elem = await element.query_selector('img')
                                
                                name = await name_elem.inner_text() if name_elem else ""
                                price = await price_elem.inner_text() if price_elem else ""
                                description = await desc_elem.inner_text() if desc_elem else ""
                                img_src = await img_elem.get_attribute('src') if img_elem else ""
                                
                                if name and (price or description):
                                    product = {
                                        "name": name.strip(),
                                        "price": price.strip() if price else None,
                                        "description": description.strip() if description else None,
                                        "product_url": url,
                                        "image_urls": [self._normalize_url(img_src, url)] if img_src else [],
                                        "features": [],
                                        "category": None,
                                        "availability": None
                                    }
                                    products.append(product)
                                    
                            except Exception as inner_e:
                                logger.debug(f"Error extracting individual product: {str(inner_e)}")
                                continue
                                
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {str(e)}")
                        continue
                
                await browser.close()
                return products[:20]  # Limit to 20 products per page
                
        except Exception as e:
            logger.error(f"Error in custom product extraction: {str(e)}")
            return []

    async def _smart_scraper_extract_products(self, url: str) -> List[Dict[str, Any]]:
        """
        Use SmartScraperGraph to extract products.
        
        Args:
            url: URL to extract products from
            
        Returns:
            List of product information
        """
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor, 
                    self._run_smart_scraper_products_in_thread, 
                    url
                )
                
                if result and isinstance(result, list):
                    return result
                elif result and isinstance(result, dict) and "products" in result:
                    return result["products"]
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Error in SmartScraperGraph product extraction: {str(e)}")
            return []

    def _run_smart_scraper_products_in_thread(self, url: str) -> List[Dict[str, Any]]:
        """
        Run SmartScraperGraph in a separate thread to extract products.
        
        Args:
            url: URL to extract products from
            
        Returns:
            Raw extraction results from SmartScraperGraph
        """
        try:
            graph_config = self._get_graph_config()
            graph_config["browser"] = {"sync": True}
            
            smart_scraper = SmartScraperGraph(
                prompt=self._create_products_extraction_prompt(),
                source=url,
                config=graph_config
            )
            
            result = smart_scraper.run()
            
            # Process the result to ensure it's a list
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "products" in result:
                return result["products"]
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error in _run_smart_scraper_products_in_thread: {str(e)}")
            return []

    async def extract_complete_pricing_info(self, website_url: str) -> Dict[str, Any]:
        """
        Complete pricing extraction process for a competitor website.
        
        Args:
            website_url: The URL of the competitor website
            
        Returns:
            Dictionary containing all pricing information found
        """
        try:
            logger.info(f"Starting complete pricing extraction for: {website_url}")
            
            # Step 1: Find pricing and product URLs
            url_info = await self.find_pricing_urls(website_url)
            
            # Step 2: Extract products from each URL
            all_products = []
            all_urls = list(set(url_info["pricing_urls"] + url_info["products_urls"] + [website_url]))
            
            for url in all_urls[:10]:  # Limit to 10 URLs to avoid overload
                try:
                    products = await self.extract_products_from_url(url)
                    for product in products:
                        product["source_url"] = url
                        # Parse price information
                        if product.get("price"):
                            price, currency, is_range, min_price, max_price = self._parse_price(product["price"])
                            product["parsed_price"] = price
                            product["currency"] = currency
                            product["is_range"] = is_range
                            product["min_price"] = min_price
                            product["max_price"] = max_price
                    
                    all_products.extend(products)
                except Exception as e:
                    logger.error(f"Error extracting from {url}: {str(e)}")
                    continue
            
            return {
                "website_url": website_url,
                "pricing_urls": url_info["pricing_urls"],
                "products_urls": url_info["products_urls"],
                "products": all_products,
                "total_products": len(all_products)
            }
            
        except Exception as e:
            logger.error(f"Error in complete pricing extraction: {str(e)}")
            return {
                "website_url": website_url,
                "pricing_urls": [],
                "products_urls": [],
                "products": [],
                "total_products": 0,
                "error": str(e)
            }

# Utility function for direct usage
async def extract_competitor_pricing(
    website_url: str,
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Utility function to extract pricing information from a competitor website.
    
    Args:
        website_url: The URL of the competitor website
        llm_provider: The LLM provider to use
        llm_model: The model to use for extraction
        api_key: API key for the LLM provider
        
    Returns:
        Dictionary containing extracted pricing information
    """
    scraper = CompetitorPricingScraper(
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key=api_key,
        headless=True
    )
    
    return await scraper.extract_complete_pricing_info(website_url) 