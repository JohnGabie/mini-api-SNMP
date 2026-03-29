import asyncio
from typing import Optional

from fastapi import APIRouter, Query

from app.core.logger import LOG_BUFFER
from app.services import snmp_service, discovery_service

router = APIRouter(tags=["debug"])


@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: Optional[str] = Query(None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
    search: Optional[str] = Query(None, description="Text search in message"),
):
    logs = list(LOG_BUFFER)

    if level:
        logs = [entry for entry in logs if entry["level"] == level.upper()]
    if search:
        logs = [entry for entry in logs if search.lower() in entry["message"].lower()]

    # Return most recent `limit` entries
    return {"total": len(logs), "logs": logs[-limit:]}


@router.get("/debug/snmp-test")
async def snmp_test():
    result = await asyncio.to_thread(snmp_service.raw_connection_test)
    return result


@router.get("/debug/arp-scan")
async def arp_scan():
    result = await asyncio.to_thread(discovery_service.run_arp_scan_raw)
    return result
