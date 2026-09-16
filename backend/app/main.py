"""
Main FastAPI application entrypoint.
Village-Level Weather Downscaling & Agro-Advisory Platform
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.api import router
from backend.app.services.spatial_service import spatial_service
from backend.app.services.forecast_service import forecast_service
from backend.app.services.advisory_service import advisory_service

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validates and warms up services on application startup."""
    print("=" * 70)
    print(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"   Indexed {spatial_service.total_villages} Kerala Panchayats & Municipalities")
    model_status = "Loaded & Ready" if forecast_service.pipeline.correction_model.is_trained else "Untrained"
    print(f"   ML Correction Model: {model_status}")
    print(f"   Agro-Advisory Engine: Loaded ({len(advisory_service.engine.rules)} active rules)")
    print(f"   Interactive Docs available at: http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 70)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade backend API connecting high-resolution spatial downscaling (IDW + Random Forest ML) "
        "and agro-climatic advisory rule engines for 1,031 Panchayats across Kerala, India."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.api.crop_routes import crop_router

# Include API Routers
app.include_router(router, prefix=settings.API_PREFIX)
app.include_router(crop_router, prefix=settings.API_PREFIX)



@app.get("/", include_in_schema=False)
def root():
    """Redirect root path to interactive OpenAPI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
