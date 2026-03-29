import logging

from fastapi import APIRouter, HTTPException

from app.services import snmp_service
from app.websocket.manager import ws_manager

logger = logging.getLogger("mini_api_snmp.api")

router = APIRouter(prefix="/outlets", tags=["outlets"])


def _validate(outlet: int) -> None:
    if not (1 <= outlet <= snmp_service.OUTLET_COUNT):
        raise HTTPException(
            status_code=422,
            detail=f"outlet must be between 1 and {snmp_service.OUTLET_COUNT}",
        )


def _state_label(state: bool | None) -> str:
    if state is True:
        return "ON"
    if state is False:
        return "OFF"
    return "UNKNOWN"


@router.get("")
async def list_outlets():
    states = await snmp_service.get_all_outlets()
    return {
        "outlets": [
            {"outlet": i, "state": _state_label(s)}
            for i, s in states.items()
        ]
    }


@router.get("/{outlet}")
async def get_outlet(outlet: int):
    _validate(outlet)
    state = await snmp_service.get_status_async(outlet)
    if state is None:
        raise HTTPException(status_code=503, detail="failed to read outlet state")
    return {"outlet": outlet, "state": _state_label(state)}


@router.post("/{outlet}/on")
async def turn_on(outlet: int):
    _validate(outlet)
    success = await snmp_service.turn_on_async(outlet)
    if not success:
        raise HTTPException(status_code=503, detail="SNMP command failed")
    state = await snmp_service.get_status_async(outlet)
    label = _state_label(state)
    await ws_manager.broadcast("outlet_state_changed", outlet=outlet, state=label)
    return {"outlet": outlet, "state": label}


@router.post("/{outlet}/off")
async def turn_off(outlet: int):
    _validate(outlet)
    success = await snmp_service.turn_off_async(outlet)
    if not success:
        raise HTTPException(status_code=503, detail="SNMP command failed")
    state = await snmp_service.get_status_async(outlet)
    label = _state_label(state)
    await ws_manager.broadcast("outlet_state_changed", outlet=outlet, state=label)
    return {"outlet": outlet, "state": label}
