from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log the incoming request details
    logger.info(f"REQUEST PATH: {request.method} {request.url.path}")
    logger.info(f"REQUEST QUERY PARAMS: {request.query_params}")
    
    # Try to log headers and body if needed
    logger.info(f"REQUEST HEADERS: {request.headers.get('content-type', 'none')}")
    
    # Continue processing the request
    response = await call_next(request)
    
    # Log response details
    process_time = time.time() - start_time
    logger.info(f"RESPONSE STATUS: {response.status_code}")
    logger.info(f"PROCESSING TIME: {process_time:.4f}s")
    
    return response

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to Business AI API"}