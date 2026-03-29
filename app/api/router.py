from fastapi import APIRouter

from app.api import outlets, health, debug
from app.websocket import routes as ws_routes

router = APIRouter()
router.include_router(health.router)
router.include_router(outlets.router)
router.include_router(debug.router)
router.include_router(ws_routes.router)
