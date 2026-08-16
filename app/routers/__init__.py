from app.routers.patients import router as patients_router
from app.routers.auth import router as auth_router
from app.routers.records import router as records_router

__all__ = ["patients_router", "auth_router", "records_router"]
