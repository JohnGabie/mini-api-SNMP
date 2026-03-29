# mini-api-SNMP

Local SNMP proxy API that bridges **Zion Hub** to a physical power strip on the local network. Since Zion Hub cannot reach SNMP devices directly, it calls this API over HTTP or WebSocket — and this API translates those calls into SNMP commands.

```
[Zion Hub] ──HTTP/WS──> [mini-api-SNMP] ──SNMP──> [Power strip]
```

---

## Features

- Turn individual outlets on/off (1–10)
- Read outlet state confirmed directly from hardware (not cached)
- Real-time WebSocket events on state changes and monitoring ticks
- Background monitoring loop detecting changes automatically
- IP auto-discovery via MAC address when the device changes IP (DHCP)
- Structured in-memory log buffer accessible remotely via API
- Remote debug endpoints for SNMP and network diagnostics

---

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI + Uvicorn |
| Config | pydantic-settings (`.env`) |
| SNMP | subprocess (`snmpset` / `snmpget`, SNMPv2c) |
| IP discovery | `ip neigh` → `arp-scan` fallback |
| WebSocket | Starlette native |
| Infra | Docker + Docker Compose |

---

## Project Structure

```
app/
├── main.py                      # FastAPI app + lifespan (start/stop monitoring)
├── core/
│   ├── config.py                # All settings loaded from .env
│   └── logger.py                # Logging setup + in-memory circular buffer
├── services/
│   ├── snmp_service.py          # SNMP commands (on/off/status/test)
│   ├── discovery_service.py     # IP auto-discovery via MAC address
│   └── monitoring_service.py   # Background loop, state tracking, WS broadcast
├── api/
│   ├── outlets.py               # GET/POST /outlets
│   ├── health.py                # GET /health
│   ├── debug.py                 # GET /logs, /debug/snmp-test, /debug/arp-scan
│   └── router.py                # Aggregates all routers
└── websocket/
    ├── manager.py               # ConnectionManager (broadcast to all clients)
    └── routes.py                # WS /ws endpoint
```

---

## SNMP OID Logic

Outlet number maps to OID: `{base_oid}.{outlet + 8}.0`

| Outlet | OID suffix |
|--------|-----------|
| 1 | `.9.0` |
| 2 | `.10.0` |
| ... | ... |
| 10 | `.18.0` |

Commands:
- Turn ON: `snmpset -v2c -c {community} {ip} {oid} i 1`
- Turn OFF: `snmpset -v2c -c {community} {ip} {oid} i 0`
- Read state: `snmpget -v2c -c {community} {ip} {oid}` → parses `INTEGER: 1` (ON) or `INTEGER: 0` (OFF)
- Connectivity test: OID `1.3.6.1.2.1.1.1.0` (sysDescr — universal)

---

## API Reference

### REST

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | API status, device connectivity, WebSocket clients, current IP |
| `GET` | `/outlets` | State of all 10 outlets (parallel reads) |
| `GET` | `/outlets/{n}` | State of a single outlet (1–10) |
| `POST` | `/outlets/{n}/on` | Turn outlet on, confirms state from hardware |
| `POST` | `/outlets/{n}/off` | Turn outlet off, confirms state from hardware |
| `GET` | `/logs` | Recent log entries from in-memory buffer |
| `GET` | `/debug/snmp-test` | Raw SNMP connectivity test (returns subprocess output) |
| `GET` | `/debug/arp-scan` | ARP scan on local network (for IP discovery debug) |

**Query params for `/logs`:**

| Param | Default | Description |
|-------|---------|-------------|
| `limit` | `100` | Max entries to return (1–1000) |
| `level` | — | Filter by level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `search` | — | Text search in message |

### WebSocket

```
WS /ws
```

Connect once and receive real-time events as JSON:

```json
{ "event": "outlet_state_changed",        "outlet": 3,   "state": "ON",      "timestamp": "..." }
{ "event": "device_connectivity_changed",  "status": "OFFLINE",  "ip": "...", "timestamp": "..." }
{ "event": "device_ip_changed",            "old_ip": "...", "new_ip": "...",   "timestamp": "..." }
{ "event": "monitoring_tick",              "outlets": [...],                   "timestamp": "..." }
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Default | Description |
|----------|---------|-------------|
| `SNMP_IP` | — | IP address of the SNMP power strip |
| `SNMP_PORT` | `161` | SNMP port |
| `SNMP_COMMUNITY` | — | SNMPv2c community string |
| `SNMP_BASE_OID` | — | Base OID of the device |
| `SNMP_MAC_ADDRESS` | — | MAC address used for IP auto-discovery |
| `SNMP_TIMEOUT` | `5` | Timeout in seconds for SNMP commands |
| `SNMP_RETRIES` | `3` | Retry count for SNMP commands |
| `MONITORING_INTERVAL` | `30` | Seconds between monitoring cycles |
| `PORT` | `8001` | HTTP port the API listens on |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

---

## Running

### Docker (recommended)

```bash
git clone <repo-url>
cd mini-api-SNMP

cp .env.example .env
# Edit .env with real values

docker compose up -d
```

The container uses `network_mode: host` so it can reach SNMP devices and run `arp-scan` on the local network directly.

Check if it's up:

```bash
curl http://localhost:8001/health
```

Logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

### Without Docker (local dev)

Requirements: Python 3.12+, `snmp` and `arp-scan` installed on the host.

```bash
# Install snmp tools (Debian/Ubuntu)
sudo apt install snmp arp-scan

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with real values

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## IP Auto-Discovery

When the SNMP device becomes unreachable, the monitoring service automatically scans the local network to find it by MAC address:

1. Checks ARP neighbor cache (`ip neigh show`) — fast, no root required
2. Falls back to `arp-scan --localnet` — requires `NET_RAW` capability (included in Docker config)
3. If found at a new IP, updates in-memory config and broadcasts a `device_ip_changed` WebSocket event

Configure `SNMP_MAC_ADDRESS` in `.env` to enable this feature.

---

## Zion Hub Integration

This section describes how Zion Hub should consume this API.

### Base URL

The API is only accessible over Tailscale — it does not listen on the public internet or the local internal network.

```
http://100.91.86.31:8001
ws://100.91.86.31:8001/ws
```

### 1. Health check

Poll this on Zion Hub startup and periodically to confirm the bridge is reachable before sending commands.

```http
GET /health
```

```json
{
  "status": "ok",
  "device": { "ip": "192.168.101.6", "connectivity": "ONLINE" },
  "websocket": { "active_connections": 1 },
  "timestamp": "2026-03-29T03:41:07.044356+00:00"
}
```

### 2. WebSocket connection

Connect **once** on Zion Hub startup and keep the connection alive. This is the primary channel — instead of polling, Zion Hub reacts to events pushed by the bridge.

```
WS ws://100.91.86.31:8001/ws
```

Handle these events:

| Event | When | What Zion Hub should do |
|-------|------|------------------------|
| `outlet_state_changed` | Outlet changed state (detected by monitoring or after a command) | Update the outlet state in Zion Hub's database |
| `monitoring_tick` | Every monitoring cycle | Use as a full state sync / heartbeat |
| `device_connectivity_changed` | Strip went ONLINE or OFFLINE | Mark strip as unavailable; when it comes back ONLINE, trigger state restoration |
| `device_ip_changed` | Strip changed IP (DHCP) | Log it — the bridge handles it automatically, no action needed |

**State restoration after power loss:**
When `device_connectivity_changed` with `status: ONLINE` is received, Zion Hub knows the strip just came back online with all outlets ON by default. It should immediately send the correct `on`/`off` commands for each outlet to restore the expected state.

### 3. Controlling outlets

```http
POST /outlets/{n}/on
POST /outlets/{n}/off
```

Response confirms the real hardware state after the command:

```json
{ "outlet": 4, "state": "ON" }
```

Outlets are numbered **1–10**. Returns `503` if the SNMP command fails.

### 4. Reading outlet state

```http
GET /outlets        → all 10 outlets in parallel
GET /outlets/{n}    → single outlet
```

Use this for the initial sync when Zion Hub starts or reconnects.

### 5. Suggested integration flow

```
Zion Hub starts
  ├── GET /health → confirm bridge is reachable
  ├── GET /outlets → sync initial state of all outlets into local DB
  └── WS /ws → open persistent connection

On WS event "outlet_state_changed"
  └── update outlet state in Zion Hub DB

On WS event "device_connectivity_changed" { status: "ONLINE" }
  └── for each outlet → POST /outlets/{n}/on or /off to restore expected state

On WS disconnect
  └── reconnect with exponential backoff

User action in Zion Hub (toggle outlet)
  └── POST /outlets/{n}/on or /off → update DB with confirmed state from response
```

---

## Observability

All operations are logged with timestamp, level, logger name and message. The log buffer holds the last 1000 entries in memory and is accessible without SSH:

```bash
# All recent logs
curl http://100.91.86.31:8001/logs

# Only errors
curl "http://100.91.86.31:8001/logs?level=ERROR"

# Search by keyword
curl "http://100.91.86.31:8001/logs?search=outlet+4"

# Raw SNMP connectivity test
curl http://100.91.86.31:8001/debug/snmp-test

# Network scan (see all devices + MACs on the local network)
curl http://100.91.86.31:8001/debug/arp-scan
```
