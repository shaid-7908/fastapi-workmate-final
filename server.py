import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "app"))

from config.env_config import env_config
from config.db_config import connect_db, disconnect_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting FastAPI WorkMate application...")
    logger.info(f"Environment: {env_config.HOST_ENVIORMENT}")
    logger.info(f"Port: {env_config.PORT}")
    
    # Initialize database connection - app will not start if this fails
    logger.info("Connecting to database...")
    await connect_db()
    logger.info("Database connection established successfully")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI WorkMate application...")
    
    # Close database connections
    await disconnect_db()
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="WorkMate API",
    description="A comprehensive work management and collaboration platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if env_config.HOST_ENVIORMENT == "development" else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP error occurred: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "message": "Validation error",
            "details": exc.errors(),
            "status_code": 422,
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "status_code": 500,
            "path": str(request.url)
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "WorkMate API is running",
        "version": "1.0.0",
        "environment": env_config.HOST_ENVIORMENT
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to WorkMate API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


# API routes will be added here
# Example structure for future routes:
# from route.auth_routes import auth_router
# from route.user_routes import user_router
# from route.project_routes import project_router
# 
# app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
# app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
# app.include_router(project_router, prefix="/api/v1/projects", tags=["Projects"])


if __name__ == "__main__":
    # Get port from environment or default to 8000
    port = int(env_config.PORT) if env_config.PORT else 8000
    
    # Run the application
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True if env_config.HOST_ENVIORMENT == "development" else False,
        log_level="info",
        access_log=True
    )
