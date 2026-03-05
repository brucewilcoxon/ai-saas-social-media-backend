from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.tenants.router import router as tenants_router
from app.modules.agencies.router import router as agencies_router
from app.modules.clients.router import router as clients_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.posts.router import router as posts_router
from app.modules.social.router import router as social_router
from app.modules.stripe.router import router as stripe_router
from app.modules.scheduler.router import router as scheduler_router

app = FastAPI(
    title="Nervia AI API",
    description="SaaS platform for AI-powered social media campaign management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
# Handle wildcard origin: if "*" is specified, don't set allow_credentials (FastAPI limitation)
cors_origins = settings.cors_origins_list
cors_credentials = True

# If wildcard is used, we can't use credentials (FastAPI requirement)
# But for development with port forwarding, we'll allow common localhost origins
if "*" in cors_origins:
    # For development: allow common localhost origins when using port forwarding
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://app.nervia.io",
        "https://www.app.nervia.io",
    ]
    cors_credentials = True

# Always allow production domain if specified
production_domain = "https://app.nervia.io"
if production_domain not in cors_origins:
    cors_origins.append(production_domain)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(tenants_router, prefix="/api")
app.include_router(agencies_router, prefix="/api")
app.include_router(clients_router, prefix="/api")
app.include_router(campaigns_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(social_router, prefix="/api")
app.include_router(stripe_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Nervia AI API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
