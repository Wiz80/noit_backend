from fastapi import FastAPI, Request, Depends
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

# Configurar CORS para permitir solicitudes desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://noit.com.co",
        "https://www.noit.com.co",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost", 
        "http://localhost:4321",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://186.29.213.230",
        "https://186.29.213.230",
        "http://186.29.213.230:4321",
        "http://186.84.88.139",
        "https://186.84.88.139",
        "null"
    ],  
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    logger.info(f"REQUEST ORIGIN: {request.headers.get('origin', 'none')}")
    
    # Continue processing the request
    response = await call_next(request)
    
    # Log response details
    process_time = time.time() - start_time
    logger.info(f"RESPONSE STATUS: {response.status_code}")
    logger.info(f"PROCESSING TIME: {process_time:.4f}s")
    
    return response

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to Infinity Lab API"}

@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    Services like MinIO are now configured for lazy loading, meaning they will only
    initialize connections when actually needed, not during application startup.
    This significantly improves the startup time of the application.
    """
    logger.info("Starting application with optimized lazy-loading services")
    logger.info("Services like MinIO will only connect when actually needed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 