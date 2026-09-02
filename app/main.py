from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import init_db, get_db, async_session
from app.routes import auth_router, doctors_router, appointments_router, admin_router
from app.models import User, UserRole
from app.security import hash_password

settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    await init_db()
    
    # Create default admin if not exists
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
        if not result.scalar_one_or_none():
            admin = User(
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
            await db.commit()
            print(f"Default admin created: {settings.admin_email}")
    
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Medical Appointment API",
    description="Secure API for managing medical appointments",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = settings.allowed_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
)


# Security headers middleware (relaxed for Swagger UI)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Skip strict CSP for docs endpoints
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        return response
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Don't expose internal validation details."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Invalid request data"},
    )


# Include routers
app.include_router(auth_router)
app.include_router(doctors_router)
app.include_router(appointments_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Medical Appointment API"}


@app.get("/health")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def health_check(request: Request):
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }
