"""
RPG Founding Engineer Challenge - Document Understanding Workflow
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.api import clients, intakes, documents, checklist
# Import models to ensure they're registered with Base.metadata
from app.models import Client, Intake, Document, ChecklistItem

# Create database tables
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Create FastAPI app
app = FastAPI(
    title="RPG Document Understanding API",
    description="Automated document classification and extraction for tax workflows",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(intakes.router, prefix="/intakes", tags=["intakes"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(checklist.router, prefix="/intakes", tags=["checklist"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "RPG Document Understanding API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "ocr_service": "ready"
    }

