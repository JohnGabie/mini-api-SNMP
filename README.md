# mini-api-SNMP

Local SNMP proxy API that bridges the **Zion Hub** backend to a physical power strip on the local network. Zion Hub cannot reach SNMP devices directly, so it calls this API over HTTP/WebSocket — this API translates those calls into SNMP commands.

```
[Zion Hub] ──HTTP/WS──> [mini-api-SNMP] ──SNMP──> [Power strip]
```

---

## Features

- Turn individual outlets on/off (1–10)
- Read outlet state (ON/OFF) and device connectivity
- Real-time WebSocket events on state changes
- Background monitoring loop with automatic state sync
- IP auto-discovery via MAC address when the device changes IP
- Structured logging with remote debug endpoints

---

## Requirements

- Docker + Docker Compose
- `snmp-utils` and `arp-scan` available on the host (or inside the container)
- Access to the same local network as the SNMP device

---

## Setup

```bash
git clone <repo-url>
cd mini-api-SNMP

cp .env.example .env
# Edit .env with your actual SNMP device values

docker compose up -d
```

---

## Environment Variables

See `.env.example` for all required fields.

| Variable | Description |
|----------|-------------|
| `SNMP_IP` | IP address of the SNMP power strip |
| `SNMP_PORT` | SNMP port (default: `161`) |
| `SNMP_COMMUNITY` | SNMPv2c community string |
| `SNMP_BASE_OID` | Base OID of the device |
| `SNMP_MAC_ADDRESS` | MAC address for IP auto-discovery |
| `SNMP_TIMEOUT` | Timeout in seconds for SNMP commands (default: `5`) |
| `SNMP_RETRIES` | Retry count for SNMP commands (default: `3`) |
| `MONITORING_INTERVAL` | Seconds between monitoring cycles (default: `30`) |
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## API Endpoints

### REST

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API status + device connectivity + IP in use |
| `GET` | `/outlets` | State of all 10 outlets (parallel reads) |
| `GET` | `/outlets/{n}` | State of outlet `n` (1–10) |
| `POST` | `/outlets/{n}/on` | Turn outlet `n` on |
| `POST` | `/outlets/{n}/off` | Turn outlet `n` off |
| `GET` | `/logs` | Recent logs (`?limit=50&level=ERROR`) |
| `GET` | `/debug/snmp-test` | Raw SNMP connectivity test |
| `GET` | `/debug/arp-scan` | ARP scan on local network |

### WebSocket

```
WS /ws
```

---

## WebSocket Events

```json
{ "event": "outlet_state_changed",       "outlet": 3,   "state": "ON"    }
{ "event": "device_connectivity_changed", "status": "OFFLINE"             }
{ "event": "device_ip_changed",           "old_ip": "...", "new_ip": "..." }
{ "event": "monitoring_tick",             "outlets": [...]                 }
```

---

## SNMP OID Logic

Outlet number maps to OID via: `{base_oid}.{outlet + 8}.0`

- Outlet 1 → `{base_oid}.9.0`
- Outlet 10 → `{base_oid}.18.0`

---

## Development

```bash
# Run locally without Docker
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
