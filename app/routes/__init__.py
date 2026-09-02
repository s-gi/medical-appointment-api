from .auth import router as auth_router
from .doctors import router as doctors_router
from .appointments import router as appointments_router
from .admin import router as admin_router

__all__ = [
    "auth_router",
    "doctors_router",
    "appointments_router",
    "admin_router",
]
