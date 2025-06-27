from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints import crud
from app.api import deps
from app.schemas.business.competitor_pricing import (
    CompetitorPricingExtractionRequest,
    SingleCompetitorPricingRequest,
    PricingExtractionResponse,
    BatchPricingExtractionResponse,
    CompetitorPricingAnalysisResponse,
    CompetitorPricingComparison,
    ProductSearchFilter,
    ProductSearchResponse,
    CompetitorProduct,
    CompetitorPricingExtraction,
    PricingStatusEnum
)
from app.models.business.competitive_analysis.competitors import Competitor
from app.controllers.competitive_analysis.competitor_pricing_controller import CompetitorPricingController
from app.services.business.competitive_analysis.latin_america_config import CountryConfig, get_search_terms

router = APIRouter()

# Add Latin America specific endpoints

@router.get("/config/countries")
def get_supported_countries(
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get list of supported Latin American countries with their configurations.
    """
    countries = ["CO", "MX", "AR", "BR", "PE", "CL"]
    country_configs = {}
    
    for country_code in countries:
        config = CountryConfig.get_country_config(country_code)
        country_configs[country_code] = {
            "name": config["name"],
            "currency": config["currency"],
            "currency_symbol": config["currency_symbol"]
        }
    
    return {
        "supported_countries": country_configs,
        "default_country": "CO",
        "default_language": "es"
    }

@router.get("/config/search-terms")
def get_search_terms_for_language(
    language: str = Query("es", description="Language code (es, pt, en)"),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get search terms for the specified language.
    """
    try:
        terms = get_search_terms(language)
        return {
            "language": language,
            "pricing_terms": terms["pricing"],
            "product_terms": terms["products"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

@router.post("/extract/batch", response_model=BatchPricingExtractionResponse)
def extract_pricing_batch(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    request: CompetitorPricingExtractionRequest,
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Extract pricing information for multiple competitors.
    
    This endpoint starts a background task to extract pricing information
    from competitor websites for a specific business idea.
    """
    try:
        # Get competitors for the business
        if request.competitor_ids:
            competitors = []
            for competitor_id in request.competitor_ids:
                competitor = crud.competitor.get_by_business_and_id(
                    db, business_id=business_id, competitor_id=competitor_id
                )
                if competitor:
                    competitors.append(competitor)
        else:
            # Get all competitors for the business
            competitors = crud.competitor.get_by_business(db, business_id=business_id)

        if not competitors:
            raise HTTPException(
                status_code=404, 
                detail="No competitors found for the specified business"
            )

        # Initialize controller
        controller = CompetitorPricingController(db)
        
        # Start batch extraction
        task_id = controller.start_batch_extraction(
            business_id=business_id,
            competitors=competitors,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            update_existing=request.update_existing,
            background_tasks=background_tasks
        )

        return BatchPricingExtractionResponse(
            task_id=task_id,
            status="started",
            competitors_processed=[c.id for c in competitors],
            message=f"Started pricing extraction for {len(competitors)} competitors"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract/single", response_model=PricingExtractionResponse)
def extract_pricing_single(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    request: SingleCompetitorPricingRequest,
    background_tasks: BackgroundTasks,
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Extract pricing information for a single competitor.
    """
    try:
        # Get competitor
        competitor = crud.competitor.get_by_business_and_id(
            db, business_id=business_id, competitor_id=request.competitor_id
        )
        if not competitor:
            raise HTTPException(
                status_code=404, 
                detail="Competitor not found for the specified business"
            )

        # Initialize controller
        controller = CompetitorPricingController(db)
        
        # Start single extraction
        extraction_id = controller.start_single_extraction(
            competitor=competitor,
            website_url=request.website_url,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            background_tasks=background_tasks
        )

        return PricingExtractionResponse(
            extraction_id=extraction_id,
            status="started",
            message=f"Started pricing extraction for competitor {competitor.competitor_name}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analysis", response_model=CompetitorPricingComparison)
def get_pricing_analysis(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    competitor_ids: List[str] = Query(None),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get comprehensive pricing analysis for competitors.
    """
    try:
        controller = CompetitorPricingController(db)
        analysis = controller.get_pricing_analysis(
            business_id=business_id,
            competitor_ids=competitor_ids
        )
        return analysis

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products/search", response_model=ProductSearchResponse)
def search_products(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    competitor_ids: List[str] = Query(None),
    product_types: List[str] = Query(None),
    min_price: float = Query(None),
    max_price: float = Query(None),
    currency: str = Query(None),
    categories: List[str] = Query(None),
    search_term: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Search products with advanced filtering.
    """
    try:
        filters = ProductSearchFilter(
            competitor_ids=competitor_ids,
            product_types=product_types,
            min_price=min_price,
            max_price=max_price,
            currency=currency,
            categories=categories,
            search_term=search_term,
            limit=limit,
            offset=offset
        )

        products, total = crud.competitor_product.search_products(
            db, business_id=business_id, filters=filters
        )

        return ProductSearchResponse(
            products=products,
            total=total,
            limit=limit,
            offset=offset,
            filters_applied=filters
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/competitors/{competitor_id}/products", response_model=List[CompetitorProduct])
def get_competitor_products(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    competitor_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get all products for a specific competitor.
    """
    try:
        # Verify competitor belongs to business
        competitor = crud.competitor.get_by_business_and_id(
            db, business_id=business_id, competitor_id=competitor_id
        )
        if not competitor:
            raise HTTPException(
                status_code=404, 
                detail="Competitor not found for the specified business"
            )

        products = crud.competitor_product.get_by_competitor(
            db, competitor_id=competitor_id, skip=skip, limit=limit
        )
        return products

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/extractions", response_model=List[CompetitorPricingExtraction])
def get_extractions(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    status: PricingStatusEnum = Query(None),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get all pricing extraction records for a business.
    """
    try:
        extractions = crud.competitor_pricing_extraction.get_by_business(
            db, business_id=business_id, status=status
        )
        return extractions

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/extractions/{extraction_id}", response_model=CompetitorPricingExtraction)
def get_extraction(
    *,
    db: Session = Depends(deps.get_db),
    extraction_id: str,
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get a specific pricing extraction record.
    """
    try:
        extraction = crud.competitor_pricing_extraction.get(db, id=extraction_id)
        if not extraction:
            raise HTTPException(status_code=404, detail="Extraction not found")
        
        return extraction

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/competitors/{competitor_id}/products")
def delete_competitor_products(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    competitor_id: str,
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Delete all products for a specific competitor.
    """
    try:
        # Verify competitor belongs to business
        competitor = crud.competitor.get_by_business_and_id(
            db, business_id=business_id, competitor_id=competitor_id
        )
        if not competitor:
            raise HTTPException(
                status_code=404, 
                detail="Competitor not found for the specified business"
            )

        deleted_count = crud.competitor_product.delete_by_competitor(
            db, competitor_id=competitor_id
        )
        
        return {"message": f"Deleted {deleted_count} products for competitor {competitor.competitor_name}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics", response_model=dict)
def get_pricing_statistics(
    *,
    db: Session = Depends(deps.get_db),
    business_id: str,
    competitor_ids: List[str] = Query(None),
    current_user: Any = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Get pricing statistics for competitors.
    """
    try:
        stats = crud.competitor_product.get_pricing_statistics(
            db, business_id=business_id, competitor_ids=competitor_ids
        )
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 