import asyncio
import logging
import subprocess
from typing import Optional

from app.core.config import settings
from app.services.discovery_service import get_current_ip

logger = logging.getLogger("mini_api_snmp.snmp")

OUTLET_COUNT = 10


def _build_oid(outlet: int) -> str:
    base = settings.SNMP_BASE_OID.rstrip(".")
    return f"{base}.{outlet + 8}.0"


def _run(cmd: list[str]) -> dict:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.SNMP_TIMEOUT,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error(f"SNMP timeout: {' '.join(cmd)}")
        return {"success": False, "stdout": "", "stderr": "timeout", "returncode": -1}
    except Exception as e:
        logger.error(f"SNMP error: {e}")
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def turn_on(outlet: int) -> bool:
    oid = _build_oid(outlet)
    result = _run([
        "snmpset", "-v2c",
        "-c", settings.SNMP_COMMUNITY,
        get_current_ip(),
        oid, "i", "1",
    ])
    if result["success"]:
        logger.info(f"outlet {outlet} → ON")
    else:
        logger.error(f"outlet {outlet} turn_on failed: {result['stderr']}")
    return result["success"]


def turn_off(outlet: int) -> bool:
    oid = _build_oid(outlet)
    result = _run([
        "snmpset", "-v2c",
        "-c", settings.SNMP_COMMUNITY,
        get_current_ip(),
        oid, "i", "0",
    ])
    if result["success"]:
        logger.info(f"outlet {outlet} → OFF")
    else:
        logger.error(f"outlet {outlet} turn_off failed: {result['stderr']}")
    return result["success"]


def get_status(outlet: int) -> Optional[bool]:
    oid = _build_oid(outlet)
    result = _run([
        "snmpget", "-v2c",
        "-c", settings.SNMP_COMMUNITY,
        get_current_ip(),
        oid,
    ])
    if not result["success"]:
        logger.warning(f"outlet {outlet} status read failed: {result['stderr']}")
        return None
    try:
        stdout = result["stdout"]
        if "INTEGER:" in stdout:
            return stdout.split("INTEGER:")[1].strip() == "1"
        logger.warning(f"unexpected SNMP output for outlet {outlet}: {stdout}")
        return None
    except Exception as e:
        logger.error(f"error parsing SNMP output: {e}")
        return None


def check_connection() -> bool:
    result = _run([
        "snmpget", "-v2c",
        "-c", settings.SNMP_COMMUNITY,
        "-t", str(settings.SNMP_TIMEOUT),
        "-r", str(settings.SNMP_RETRIES),
        get_current_ip(),
        "1.3.6.1.2.1.1.1.0",  # sysDescr — universal OID
    ])
    if not result["success"]:
        logger.warning(f"device unreachable at {get_current_ip()}: {result['stderr']}")
    return result["success"]


def raw_connection_test() -> dict:
    """Run connectivity check and return full subprocess result — used by debug endpoint."""
    ip = get_current_ip()
    oid = "1.3.6.1.2.1.1.1.0"
    result = _run([
        "snmpget", "-v2c",
        "-c", settings.SNMP_COMMUNITY,
        "-t", str(settings.SNMP_TIMEOUT),
        "-r", str(settings.SNMP_RETRIES),
        ip, oid,
    ])
    return {**result, "ip": ip, "oid": oid}


# Async wrappers for use in FastAPI route handlers
async def turn_on_async(outlet: int) -> bool:
    return await asyncio.to_thread(turn_on, outlet)


async def turn_off_async(outlet: int) -> bool:
    return await asyncio.to_thread(turn_off, outlet)


async def get_status_async(outlet: int) -> Optional[bool]:
    return await asyncio.to_thread(get_status, outlet)


async def get_all_outlets() -> dict[int, Optional[bool]]:
    """Read all outlet states in parallel."""
    tasks = [get_status_async(i) for i in range(1, OUTLET_COUNT + 1)]
    results = await asyncio.gather(*tasks)
    return {i + 1: state for i, state in enumerate(results)}
