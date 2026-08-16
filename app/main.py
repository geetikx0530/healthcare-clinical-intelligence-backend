from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.connection import check_db_connection

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend REST API for Clinical Decision Intelligence System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
from app.routers.patients import router as patients_router
from app.routers.auth import router as auth_router
from app.routers.records import router as records_router
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(records_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Clinical Decision Intelligence FastAPI Backend",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    db_info = check_db_connection()
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "database": db_info,
    }

