import asyncio
import logging
from typing import Optional

from app.core.config import settings
from app.services import snmp_service, discovery_service
from app.websocket.manager import ws_manager

logger = logging.getLogger("mini_api_snmp.monitoring")

# In-memory state — source of truth between monitoring cycles
_outlet_states: dict[int, Optional[bool]] = {i: None for i in range(1, snmp_service.OUTLET_COUNT + 1)}
_device_online: Optional[bool] = None
_task: Optional[asyncio.Task] = None


def get_device_online() -> Optional[bool]:
    return _device_online


def get_outlet_states() -> dict[int, Optional[bool]]:
    return dict(_outlet_states)


async def _try_rediscover() -> None:
    logger.info("device offline — scanning for new IP via MAC address...")
    new_ip = await asyncio.to_thread(discovery_service.scan_for_mac)
    if new_ip and new_ip != discovery_service.get_current_ip():
        old_ip = discovery_service.get_current_ip()
        discovery_service.update_ip(new_ip)
        logger.info(f"device IP updated: {old_ip} → {new_ip}")
        await ws_manager.broadcast("device_ip_changed", old_ip=old_ip, new_ip=new_ip)


async def _check_and_broadcast() -> None:
    global _device_online

    online = await asyncio.to_thread(snmp_service.check_connection)

    # Broadcast connectivity change
    if online != _device_online:
        _device_online = online
        status = "ONLINE" if online else "OFFLINE"
        logger.info(f"device connectivity: {status} ({discovery_service.get_current_ip()})")
        await ws_manager.broadcast(
            "device_connectivity_changed",
            status=status,
            ip=discovery_service.get_current_ip(),
        )

    if not online:
        await _try_rediscover()
        return

    # Read all outlets in parallel
    states = await snmp_service.get_all_outlets()

    # Detect and broadcast state changes
    for outlet, state in states.items():
        if state is not None and state != _outlet_states[outlet]:
            _outlet_states[outlet] = state
            label = "ON" if state else "OFF"
            logger.info(f"outlet {outlet} changed → {label}")
            await ws_manager.broadcast("outlet_state_changed", outlet=outlet, state=label)

    # Always broadcast full snapshot
    await ws_manager.broadcast(
        "monitoring_tick",
        outlets=[
            {"outlet": i, "state": "ON" if s else ("OFF" if s is not None else "UNKNOWN")}
            for i, s in states.items()
        ],
    )


async def _loop() -> None:
    logger.info(f"monitoring loop started (interval: {settings.MONITORING_INTERVAL}s)")
    while True:
        try:
            await _check_and_broadcast()
        except Exception as e:
            logger.error(f"monitoring error: {e}")
        await asyncio.sleep(settings.MONITORING_INTERVAL)


def start() -> None:
    global _task
    _task = asyncio.create_task(_loop())
    logger.info("monitoring service started")


def stop() -> None:
    global _task
    if _task:
        _task.cancel()
        _task = None
        logger.info("monitoring service stopped")
