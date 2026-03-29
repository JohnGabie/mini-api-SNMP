import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

from app.services import snmp_service, discovery_service
from app.services.monitoring_service import get_device_online
from app.websocket.manager import ws_manager

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    online = get_device_online()
    if online is None:
        # Monitoring hasn't run yet — check directly
        online = await asyncio.to_thread(snmp_service.check_connection)

    return {
        "status": "ok",
        "device": {
            "ip": discovery_service.get_current_ip(),
            "connectivity": "ONLINE" if online else "OFFLINE",
        },
        "websocket": {
            "active_connections": ws_manager.active_connections,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
