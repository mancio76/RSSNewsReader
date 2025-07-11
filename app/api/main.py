from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import logging
import time
from datetime import datetime

from .routes import articles, sources, tags, statistics
from .models import ErrorResponse
from ..models.base import create_tables
from ..frontend.routes import router as frontend_router

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crea app FastAPI
app = FastAPI(
    title="RSSNewsReader API",
    description="API REST per la gestione di articoli e sources RSS",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione, specificare domini precisi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware per logging delle richieste
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log richiesta
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log risposta
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    # Aggiungi header con tempo di processo
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            timestamp=datetime.now(datetime.timezone.utc).isoformat()
        )
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_code="INTERNAL_ERROR",
            timestamp=datetime.now(datetime.timezone.utc).isoformat()
        )
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting RSSNewsReader API...")
    
    # Crea tabelle database se non esistono
    try:
        create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    
    logger.info("API startup completed")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down RSSNewsReader API...")

# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """API root endpoint with basic information"""
    return {
        "name": "RSSNewsReader API",
        "version": "1.0.0",
        "description": "API REST per la gestione di articoli e sources RSS",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "articles": "/articles",
            "sources": "/sources", 
            "tags": "/tags",
            "statistics": "/statistics"
        },
        "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
        "status": "running"
    }

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    try:
        from .dependencies import get_db
        from ..models import Article
        
        # Test database connection
        db = next(get_db())
        try:
            article_count = db.query(Article).count()
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            db_status = "unhealthy"
            article_count = 0
        finally:
            db.close()
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
            "database": db_status,
            "article_count": article_count,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
                "error": str(e)
            }
        )

# Info endpoint
@app.get("/info", tags=["info"])
async def get_api_info():
    """Get detailed API information"""
    return {
        "api_name": "RSSNewsReader API",
        "version": "1.0.0",
        "description": "API REST completa per la gestione di articoli RSS e web scraping",
        "features": [
            "Gestione articoli con filtri avanzati",
            "Gestione sources RSS e web scraping",
            "Sistema di tags e categorie",
            "Statistiche dettagliate",
            "Ricerca full-text",
            "Export dati",
            "Scraping automatico"
        ],
        "endpoints": {
            "articles": {
                "base": "/articles",
                "methods": ["GET", "PUT", "DELETE"],
                "features": ["pagination", "filtering", "search", "statistics"]
            },
            "sources": {
                "base": "/sources", 
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "features": ["CRUD", "validation", "scraping", "statistics"]
            },
            "tags": {
                "base": "/tags",
                "methods": ["GET", "POST", "DELETE"],
                "features": ["categories", "wordcloud", "trends"]
            },
            "statistics": {
                "base": "/statistics",
                "methods": ["GET"],
                "features": ["dashboard", "timeline", "trends", "export"]
            }
        },
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_schema": "/openapi.json"
        },
        "support": {
            "logging": "Structured logging with request tracing",
            "error_handling": "Comprehensive error responses",
            "cors": "Cross-origin resource sharing enabled",
            "validation": "Request/response validation with Pydantic"
        }
    }

# Include routers
app.include_router(articles.router)
app.include_router(sources.router)
app.include_router(tags.router)
app.include_router(statistics.router)
app.include_router(frontend_router)  # Frontend web interface

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="RSSNewsReader API",
        version="1.0.0",
        description="""
        ## API completa per RSSNewsReader
        
        Questa API fornisce tutti gli strumenti necessari per gestire un sistema di aggregazione RSS/Web:
        
        ### Funzionalità principali:
        - **Gestione Articoli**: CRUD completo con ricerca avanzata e filtri
        - **Gestione Sources**: Configurazione RSS e web scraping
        - **Sistema Tags**: Organizzazione contenuti con categorie
        - **Statistiche**: Dashboard e analytics dettagliate
        - **Scraping**: Automazione raccolta contenuti
        
        ### Esempi di utilizzo:
        - Aggregare notizie da multiple fonti
        - Analizzare trend e sentiment
        - Organizzare contenuti per categoria
        - Monitorare performance sources
        
        ### Autenticazione:
        Attualmente non richiesta. In produzione implementare OAuth2/JWT.
        """,
        routes=app.routes,
    )
    
    # Aggiungi info aggiuntive
    openapi_schema["info"]["contact"] = {
        "name": "RSSNewsReader Support",
        "email": "support@rssnewsreader.com"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Aggiungi tags per organizzazione
    openapi_schema["tags"] = [
        {
            "name": "articles",
            "description": "Operazioni sugli articoli - lettura, modifica, ricerca"
        },
        {
            "name": "sources", 
            "description": "Gestione sources RSS e web scraping"
        },
        {
            "name": "tags",
            "description": "Sistema di tagging e categorizzazione"
        },
        {
            "name": "statistics",
            "description": "Analytics e statistiche del sistema"
        },
        {
            "name": "root",
            "description": "Endpoints di base e informazioni API"
        },
        {
            "name": "health",
            "description": "Monitoraggio stato del sistema"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )