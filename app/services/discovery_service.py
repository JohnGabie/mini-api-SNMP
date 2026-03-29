import logging
import subprocess
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("mini_api_snmp.discovery")

# Runtime IP — may differ from .env if auto-discovery updated it
_current_ip: str = settings.SNMP_IP


def get_current_ip() -> str:
    return _current_ip


def update_ip(new_ip: str) -> None:
    global _current_ip
    _current_ip = new_ip


def _find_mac_in_output(output: str, mac: str) -> Optional[str]:
    """Return the IP on the same line as the MAC address."""
    mac_lower = mac.lower()
    for line in output.splitlines():
        if mac_lower in line.lower():
            parts = line.split()
            if parts:
                return parts[0]
    return None


def scan_for_mac() -> Optional[str]:
    """
    Search the local network for the configured MAC address.
    Tries ARP neighbor cache first (fast, no root), then arp-scan (needs NET_RAW).
    Returns the discovered IP or None.
    """
    mac = settings.SNMP_MAC_ADDRESS
    if not mac:
        logger.warning("SNMP_MAC_ADDRESS not set — skipping IP discovery")
        return None

    # 1. ARP neighbor cache (fast, no privileges needed)
    try:
        result = subprocess.run(
            ["ip", "neigh", "show"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            ip = _find_mac_in_output(result.stdout, mac)
            if ip:
                logger.info(f"device found via ARP cache: {ip}")
                return ip
    except Exception as e:
        logger.warning(f"ip neigh failed: {e}")

    # 2. arp-scan full network sweep (needs NET_RAW capability in container)
    try:
        result = subprocess.run(
            ["arp-scan", "--localnet"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            ip = _find_mac_in_output(result.stdout, mac)
            if ip:
                logger.info(f"device found via arp-scan: {ip}")
                return ip
    except FileNotFoundError:
        logger.warning("arp-scan not available")
    except Exception as e:
        logger.warning(f"arp-scan failed: {e}")

    logger.warning(f"device with MAC {mac} not found on network")
    return None


def run_arp_scan_raw() -> dict:
    """Execute network scan and return raw output — used by debug endpoint."""
    neigh_out = ""
    arp_out = ""

    try:
        r = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=5)
        neigh_out = r.stdout.strip()
    except Exception as e:
        neigh_out = f"error: {e}"

    try:
        r = subprocess.run(["arp-scan", "--localnet"], capture_output=True, text=True, timeout=30)
        arp_out = r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
    except FileNotFoundError:
        arp_out = "arp-scan not available"
    except Exception as e:
        arp_out = f"error: {e}"

    return {
        "current_ip": get_current_ip(),
        "configured_mac": settings.SNMP_MAC_ADDRESS,
        "ip_neigh": neigh_out,
        "arp_scan": arp_out,
    }
