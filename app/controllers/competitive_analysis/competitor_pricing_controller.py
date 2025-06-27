import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from decimal import Decimal

from app.api.v1.endpoints import crud
from app.models.business.competitive_analysis.competitors import Competitor
from app.models.business.competitive_analysis.competitor_products import PricingStatus
from app.schemas.business.competitor_pricing import (
    CompetitorPricingExtractionCreate,
    CompetitorProductCreate,
    CompetitorPricingComparison,
    CompetitorPricingAnalysisResponse,
    PricingInsight
)

logger = logging.getLogger(__name__)

class CompetitorPricingController:
    """Controller for managing competitor pricing extraction and analysis."""
    
    def __init__(self, db: Session):
        self.db = db

    def start_batch_extraction(
        self,
        business_id: str,
        competitors: List[Competitor],
        llm_provider: str,
        llm_model: str,
        update_existing: bool,
        background_tasks: BackgroundTasks
    ) -> str:
        """Start batch extraction for multiple competitors."""
        task_id = str(uuid.uuid4())
        
        # Create extraction records for each competitor
        for competitor in competitors:
            if update_existing or not self._has_existing_extraction(competitor.id):
                extraction = CompetitorPricingExtractionCreate(
                    competitor_id=competitor.id,
                    business_id=business_id,
                    status=PricingStatus.PENDING
                )
                crud.competitor_pricing_extraction.create_with_business(
                    self.db, obj_in=extraction
                )
        
        # Add background task
        # background_tasks.add_task(
        #     self._process_batch_extraction,
        #     business_id,
        #     [c.id for c in competitors],
        #     llm_provider,
        #     llm_model,
        #     task_id
        # )
        self._process_batch_extraction(
            business_id,
            [c.id for c in competitors],
            llm_provider,
            llm_model,
            task_id
        )

        
        return task_id

    def start_single_extraction(
        self,
        competitor: Competitor,
        website_url: Optional[str],
        llm_provider: str,
        llm_model: str,
        background_tasks: BackgroundTasks
    ) -> str:
        """Start extraction for a single competitor."""
        # Create extraction record
        extraction = CompetitorPricingExtractionCreate(
            competitor_id=competitor.id,
            business_id=competitor.business_idea_id,
            status=PricingStatus.PENDING
        )
        extraction_record = crud.competitor_pricing_extraction.create_with_business(
            self.db, obj_in=extraction
        )
        
        # Add background task
        background_tasks.add_task(
            self._process_single_extraction,
            competitor.id,
            website_url or competitor.website,
            llm_provider,
            llm_model,
            extraction_record.id
        )
        
        return extraction_record.id

    def get_pricing_analysis(
        self,
        business_id: str,
        competitor_ids: Optional[List[str]] = None
    ) -> CompetitorPricingComparison:
        """Get comprehensive pricing analysis for competitors."""
        try:
            # Get competitors
            if competitor_ids:
                competitors = [
                    crud.competitor.get(self.db, id=comp_id) 
                    for comp_id in competitor_ids
                ]
                competitors = [c for c in competitors if c and c.business_idea_id == business_id]
            else:
                competitors = self.db.query(Competitor).filter(
                    Competitor.business_idea_id == business_id
                ).all()

            # Get basic statistics
            stats = crud.competitor_product.get_pricing_statistics(
                self.db, business_id=business_id, competitor_ids=competitor_ids
            )

            # Build competitor analysis responses
            competitor_analyses = []
            for competitor in competitors:
                products = crud.competitor_product.get_by_competitor(
                    self.db, competitor_id=competitor.id
                )
                extraction = crud.competitor_pricing_extraction.get_by_competitor(
                    self.db, competitor_id=competitor.id
                )
                
                pricing_summary = self._calculate_competitor_pricing_summary(products)
                
                competitor_analyses.append(
                    CompetitorPricingAnalysisResponse(
                        competitor_id=competitor.id,
                        competitor_name=competitor.competitor_name,
                        website_url=competitor.website,
                        extraction=extraction,
                        products=products,
                        total_products=len(products),
                        pricing_summary=pricing_summary
                    )
                )

            # Generate insights
            insights = self._generate_pricing_insights(stats, competitors)

            return CompetitorPricingComparison(
                business_id=business_id,
                total_competitors=len(competitors),
                total_products=stats['total_products'],
                currency_distribution=stats['currency_distribution'],
                price_ranges=stats['price_statistics'],
                product_categories=stats['category_distribution'],
                insights=insights,
                competitors=competitor_analyses
            )

        except Exception as e:
            logger.error(f"Error in pricing analysis: {str(e)}")
            raise

    def _has_existing_extraction(self, competitor_id: str) -> bool:
        """Check if competitor already has an extraction."""
        extraction = crud.competitor_pricing_extraction.get_by_competitor(
            self.db, competitor_id=competitor_id
        )
        return extraction is not None

    async def _process_batch_extraction(
        self,
        business_id: str,
        competitor_ids: List[str],
        llm_provider: str,
        llm_model: str,
        task_id: str
    ):
        """Background task to process batch extraction."""
        logger.info(f"Starting batch pricing extraction for task {task_id}")
        
        for competitor_id in competitor_ids:
            try:
                competitor = crud.competitor.get(self.db, id=competitor_id)
                if competitor and competitor.website:
                    await self._extract_competitor_pricing(
                        competitor,
                        competitor.website,
                        llm_provider,
                        llm_model
                    )
                else:
                    logger.warning(f"Competitor {competitor_id} has no website URL")
                    
            except Exception as e:
                logger.error(f"Error processing competitor {competitor_id}: {str(e)}")
                # Update extraction status to error
                extraction = crud.competitor_pricing_extraction.get_by_competitor(
                    self.db, competitor_id=competitor_id
                )
                if extraction:
                    crud.competitor_pricing_extraction.update_status(
                        self.db,
                        extraction_id=extraction.id,
                        status=PricingStatus.ERROR,
                        error_message=str(e)
                    )

        logger.info(f"Completed batch pricing extraction for task {task_id}")

    async def _process_single_extraction(
        self,
        competitor_id: str,
        website_url: str,
        llm_provider: str,
        llm_model: str,
        extraction_id: str
    ):
        """Background task to process single extraction."""
        logger.info(f"Starting single pricing extraction for competitor {competitor_id}")
        
        try:
            competitor = crud.competitor.get(self.db, id=competitor_id)
            if competitor:
                await self._extract_competitor_pricing(
                    competitor,
                    website_url,
                    llm_provider,
                    llm_model,
                    extraction_id
                )
            else:
                raise Exception(f"Competitor {competitor_id} not found")
                
        except Exception as e:
            logger.error(f"Error in single extraction for competitor {competitor_id}: {str(e)}")
            crud.competitor_pricing_extraction.update_status(
                self.db,
                extraction_id=extraction_id,
                status=PricingStatus.ERROR,
                error_message=str(e)
            )

    async def _extract_competitor_pricing(
        self,
        competitor: Competitor,
        website_url: str,
        llm_provider: str,
        llm_model: str,
        extraction_id: Optional[str] = None
    ):
        """Extract pricing information for a competitor."""
        try:
            # Update status to processing
            if not extraction_id:
                extraction = crud.competitor_pricing_extraction.get_by_competitor(
                    self.db, competitor_id=competitor.id
                )
                extraction_id = extraction.id if extraction else None

            if extraction_id:
                crud.competitor_pricing_extraction.update_status(
                    self.db,
                    extraction_id=extraction_id,
                    status=PricingStatus.PROCESSING
                )

            # Import and use the scraper
            # Note: This is a simplified version since the full scraper wasn't created
            # You would use the actual CompetitorPricingScraper here
            logger.info(f"Extracting pricing from {website_url} for competitor {competitor.competitor_name}")
            
            # Placeholder for actual extraction
            # In real implementation, you would do:
            from app.services.scrape.competitor_pricing_scraper import CompetitorPricingScraper
            scraper = CompetitorPricingScraper(llm_provider, llm_model)
            result = await scraper.extract_complete_pricing_info(website_url)
            
            # For now, create a placeholder result
            result = {
                "website_url": website_url,
                "pricing_urls": [website_url],
                "products_urls": [website_url],
                "products": [],
                "total_products": 0
            }

            # Save extracted products
            products_saved = 0
            for product_data in result.get("products", []):
                try:
                    product = CompetitorProductCreate(
                        competitor_id=competitor.id,
                        business_id=competitor.business_idea_id,
                        name=product_data.get("name", "Unknown Product"),
                        description=product_data.get("description"),
                        price_text=product_data.get("price"),
                        product_url=product_data.get("product_url"),
                        image_urls=product_data.get("image_urls", []),
                        source_url=product_data.get("source_url"),
                        extraction_method="scrapegraph_ai",
                        currency=product_data.get("currency"),
                        price=product_data.get("parsed_price"),
                        is_range=product_data.get("is_range", False),
                        min_price=product_data.get("min_price"),
                        max_price=product_data.get("max_price")
                    )
                    
                    crud.competitor_product.create_with_business(self.db, obj_in=product)
                    products_saved += 1
                    
                except Exception as e:
                    logger.error(f"Error saving product: {str(e)}")

            # Update extraction record
            if extraction_id:
                crud.competitor_pricing_extraction.update_status(
                    self.db,
                    extraction_id=extraction_id,
                    status=PricingStatus.COMPLETED
                )
                
                # Update with URLs found and products count
                extraction = crud.competitor_pricing_extraction.get(self.db, id=extraction_id)
                if extraction:
                    update_data = {
                        "pricing_urls": result.get("pricing_urls", []),
                        "products_urls": result.get("products_urls", []),
                        "total_products_found": str(products_saved)
                    }
                    crud.competitor_pricing_extraction.update(
                        self.db, db_obj=extraction, obj_in=update_data
                    )

            logger.info(f"Successfully extracted {products_saved} products for competitor {competitor.competitor_name}")

        except Exception as e:
            logger.error(f"Error extracting pricing for competitor {competitor.id}: {str(e)}")
            if extraction_id:
                crud.competitor_pricing_extraction.update_status(
                    self.db,
                    extraction_id=extraction_id,
                    status=PricingStatus.ERROR,
                    error_message=str(e)
                )
            raise

    def _calculate_competitor_pricing_summary(self, products) -> Dict[str, Any]:
        """Calculate pricing summary for a competitor."""
        if not products:
            return {}

        # Group by currency
        currency_data = {}
        for product in products:
            if product.currency and product.price:
                if product.currency not in currency_data:
                    currency_data[product.currency] = []
                currency_data[product.currency].append(float(product.price))

        summary = {}
        for currency, prices in currency_data.items():
            summary[currency] = {
                "min_price": min(prices),
                "max_price": max(prices),
                "avg_price": sum(prices) / len(prices),
                "product_count": len(prices)
            }

        return summary

    def _generate_pricing_insights(self, stats: Dict[str, Any], competitors: List[Competitor]) -> List[PricingInsight]:
        """Generate pricing insights from statistics."""
        insights = []
        
        # Total products insight
        insights.append(PricingInsight(
            metric="total_products",
            value=float(stats['total_products']),
            description=f"Total of {stats['total_products']} products found across {len(competitors)} competitors"
        ))
        
        # Currency distribution insights
        if stats['currency_distribution']:
            dominant_currency = max(stats['currency_distribution'], key=stats['currency_distribution'].get)
            insights.append(PricingInsight(
                metric="dominant_currency",
                currency=dominant_currency,
                description=f"Most products are priced in {dominant_currency} ({stats['currency_distribution'][dominant_currency]} products)"
            ))
        
        # Price range insights
        for currency, price_stats in stats['price_statistics'].items():
            insights.append(PricingInsight(
                metric="price_range",
                value=price_stats['max'] - price_stats['min'],
                currency=currency,
                description=f"Price range in {currency}: ${price_stats['min']:.2f} - ${price_stats['max']:.2f} (avg: ${price_stats['avg']:.2f})"
            ))
        
        return insights 