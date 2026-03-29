# mini-api-SNMP — Requisitos

## Contexto

Esta mini API roda na VPS local (mesma rede dos dispositivos SNMP) e funciona como uma **ponte/proxy SNMP** para o **Zion Hub** — o novo sistema multi-tenant em desenvolvimento.

```
[Zion Hub Backend] ──HTTP/WS──> [mini-api-SNMP (esta VPS)] ──SNMP──> [Strip de energia física]
                                         │
                                   [IP auto-discovery via MAC]
```

O Zion Hub não consegue acessar os dispositivos SNMP diretamente (rede local), então esta API expõe um contrato HTTP + WebSocket para controle e monitoramento em tempo real.

---

## Configuração do Dispositivo

Todos os valores sensíveis ficam exclusivamente no arquivo `.env` (não versionado).
Consulte `.env.example` para ver os campos necessários.

**Outlets mapeados (nomes do sistema legado — referência):**
| Outlet | Nome |
|--------|------|
| 1 | Mesa de Som |
| 2 | Amplificador PA |
| 3 | Tomada 3 |
| 4 | Tomadas 4 |
| 5 | Tomada 5 |
| 6 | Microfone +4 |
| 7 | Tomada 7 |
| 8 | Tomada 8 |
| 9 | Retorno |
| 10 | Microfone Principal |

---

## Escopo

- Somente SNMP — sem Tuya, sem frontend, sem rotinas
- **Stateless** — sem banco de dados; hardware é fonte da verdade
- Uma única strip SNMP — 10 saídas, configurada via variáveis de ambiente
- Consumidor principal: backend do Zion Hub
- Sem autenticação — tráfego via rede privada (TSK)

---

## Requisitos Funcionais

### RF-01 — Ligar tomada
- Enviar comando ON para uma saída específica (1–10)
- Confirmar estado real após o comando (leitura de volta)

### RF-02 — Desligar tomada
- Enviar comando OFF para uma saída específica (1–10)
- Confirmar estado real após o comando

### RF-03 — Monitorar estado de uma tomada
- Ler estado atual (ON/OFF) de uma saída específica
- Retornar status de conectividade (ONLINE/OFFLINE)

### RF-04 — Monitorar estado de todas as tomadas
- Ler estado de todas as 10 saídas em **paralelo** (não sequencial)
- Retornar array com estado de cada saída

### RF-05 — Verificar conectividade do strip
- Testar se o strip SNMP está acessível
- Endpoint `/health` expondo: status da API + status do device + IP em uso + última leitura bem-sucedida

### RF-06 — WebSocket para tempo real
- Clientes se conectam via WS e recebem eventos em tempo real
- Loop de monitoramento em background (intervalo configurável, padrão 30s) que detecta mudanças de estado e transmite
- Eventos emitidos:
  - `outlet_state_changed` — quando uma saída muda de ON para OFF ou vice-versa
  - `device_connectivity_changed` — quando o strip fica ONLINE ou OFFLINE
  - `device_ip_changed` — quando o IP é atualizado automaticamente via MAC discovery

### RF-07 — IP auto-discovery via MAC address
- Quando o SNMP falha por IP inacessível, executar descoberta na rede pelo MAC address do strip
- Escanear a rede local (`arp-scan` ou equivalente) para localizar o dispositivo pelo MAC
- Atualizar o IP em uso automaticamente (em memória + arquivo de configuração)
- Emitir evento WebSocket `device_ip_changed` com o novo IP
- MAC address configurado via variável de ambiente

### RF-08 — Observabilidade e debug remoto
- Logging estruturado (JSON) de todas as operações SNMP, erros e eventos de conectividade
- Endpoint `GET /logs` — leitura dos logs recentes via API (paginado, filtrável por nível/tipo)
- Endpoint `GET /debug/snmp-test` — executa um snmpget de conectividade e retorna o resultado bruto
- Endpoint `GET /debug/arp-scan` — executa um scan de rede e retorna dispositivos encontrados
- Logs com: timestamp, operação, IP usado, outlet, resultado, latência, erro (se houver)

---

## Divisão de Responsabilidades

| Responsabilidade | mini-api-SNMP | Zion Hub |
|-----------------|:---:|:---:|
| Controle SNMP (on/off) | ✅ | — |
| Leitura de estado | ✅ | — |
| WebSocket / tempo real | ✅ | — |
| IP auto-discovery (MAC) | ✅ | — |
| Logging e debug remoto | ✅ | — |
| Restauração de estado após queda de energia | — | ✅ |
| Rotinas e agendamentos | — | ✅ |
| Gerenciamento multi-tenant | — | ✅ |
| Autenticação de usuários | — | ✅ |

> **Queda de energia:** Quando a luz cai e volta, o strip volta com todas as saídas LIGADAS. A responsabilidade de restaurar o estado original (enviar os comandos corretos para cada outlet) é do **Zion Hub**, que conhece o estado esperado. A mini-api apenas executa os comandos recebidos e notifica via WS quando detectar que o device voltou online.

---

## Endpoints

### HTTP REST
```
GET  /health                        Status da API + device + IP em uso
GET  /outlets                       Estado de todas as 10 tomadas (paralelo)
GET  /outlets/{outlet_number}       Estado de uma tomada (1-10)
POST /outlets/{outlet_number}/on    Liga tomada
POST /outlets/{outlet_number}/off   Desliga tomada

GET  /logs                          Logs recentes (query: limit, level, type)
GET  /debug/snmp-test               Teste de conectividade SNMP (retorno bruto)
GET  /debug/arp-scan                Scan ARP na rede (retorna devices encontrados)
```

### WebSocket
```
WS   /ws                            Conexão em tempo real
```

---

## Eventos WebSocket

```json
{ "event": "outlet_state_changed",      "outlet": 3, "state": "ON", "timestamp": "..." }
{ "event": "device_connectivity_changed","status": "OFFLINE", "ip": "192.168.101.6", "timestamp": "..." }
{ "event": "device_ip_changed",          "old_ip": "192.168.101.6", "new_ip": "192.168.101.9", "timestamp": "..." }
{ "event": "monitoring_tick",            "outlets": [...], "timestamp": "..." }
```

---

## Mapeamento SNMP

- Protocolo: SNMPv2c (community-based, sem auth)
- Ferramentas: `snmpset` / `snmpget` via subprocess
- Cálculo do OID: `{base_oid.rstrip('.')}.{outlet_number + 8}.0`
  - Saída 1 → `.1.3.6.1.4.1.17095.1.3.9.0`
  - Saída 10 → `.1.3.6.1.4.1.17095.1.3.18.0`
- Liga: `snmpset -v2c -c {SNMP_COMMUNITY} {SNMP_IP} {oid} i 1`
- Desliga: `snmpset -v2c -c {SNMP_COMMUNITY} {SNMP_IP} {oid} i 0`
- Lê estado: `snmpget -v2c -c {SNMP_COMMUNITY} {SNMP_IP} {oid}` → parseia `INTEGER: 1` (ON) / `INTEGER: 0` (OFF)
- Testa conectividade: `snmpget ... 1.3.6.1.2.1.1.1.0` (sysDescr — OID universal)

---

## Variáveis de Ambiente

Ver `.env.example` para todos os campos necessários. O arquivo `.env` real nunca é versionado.

---

## Stack Proposta

| Componente | Tecnologia |
|-----------|-----------|
| Framework | FastAPI (Python) |
| Servidor  | Uvicorn |
| SNMP      | subprocess (`snmpset`/`snmpget`) |
| ARP scan  | subprocess (`arp-scan` / `ip neigh`) |
| WebSocket | FastAPI / Starlette nativo |
| Config    | `pydantic-settings` + `.env` |
| Logs      | Python `logging` com handler em memória (deque circular) |
| Infra     | Docker + Docker Compose |

---

## Fora do Escopo

- Banco de dados / persistência
- Autenticação
- Múltiplos dispositivos SNMP
- Frontend
- Rotinas / agendamento
- Restauração de estado após queda de energia (responsabilidade do Zion Hub)
