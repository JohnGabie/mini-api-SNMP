from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logger import setup_logging
from app.api.router import router
from app.services import monitoring_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.LOG_LEVEL)
    monitoring_service.start()
    yield
    monitoring_service.stop()


app = FastAPI(
    title="mini-api-SNMP",
    description="Local SNMP proxy for Zion Hub",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
