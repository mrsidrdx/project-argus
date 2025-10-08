# Aegis Gateway

A production-style reverse-proxy gateway that enforces least-privilege policies on agent tool calls and emits audit-grade telemetry.

## Features

- **Reverse-Proxy Gateway**: Sits between agents and tools, enforcing policy-based access control
- **Policy-as-Code**: YAML-based policies with hot-reload capability
- **Mock Tools**: Payments and files adapters with realistic APIs
- **Structured Telemetry**: OpenTelemetry spans + JSON audit logs
- **Security**: Input validation, parameter hashing, sanitized error messages
- **Observability**: Complete tracing with Jaeger UI

## Architecture

```
Agent → Gateway → Policy Engine → Tool Adapter
                     ↓
                 Telemetry (OTel + Logs)
```

### Components

- **Gateway** (`app/gateway.py`): Main reverse-proxy endpoint
- **Policy Engine** (`app/policy/`): YAML policy loader with hot-reload
- **Adapters** (`app/adapters/`): Mock implementations for payments and files
- **Telemetry** (`app/telemetry/`): OpenTelemetry and structured JSON logging

## Quick Start

### Prerequisites

- Docker and Docker Compose
- `curl` and `jq` (for demo scripts)

### One-Command Setup

```bash
docker-compose up --build
```

This starts:
- **Aegis Gateway** on `http://localhost:8080`
- **Jaeger UI** on `http://localhost:16686`
- **OpenTelemetry Collector** (internal)

### Run Demo

```bash
# Wait for services to start, then run demo
./backend/scripts/demo.sh
```

## API Reference

### Gateway Endpoint

**`POST /tools/:tool/:action`**

**Headers:**
- `X-Agent-ID: <string>` (required)
- `X-Parent-Agent: <string>` (optional)

**Body:** JSON (tool-specific)

**Responses:**
- `200 OK` - Tool response (passthrough)
- `403 Forbidden` - `{"error": "PolicyViolation", "reason": "<human readable>"}`
- `400 Bad Request` - Invalid request
- `404 Not Found` - Unknown tool/action

### Mock Tools

#### Payments

**`POST /tools/payments/create`**
```json
{
  "amount": 1000,
  "currency": "USD", 
  "vendor_id": "V99",
  "memo": "Optional memo"
}
```

**`POST /tools/payments/refund`**
```json
{
  "payment_id": "uuid",
  "reason": "Optional reason"
}
```

#### Files

**`POST /tools/files/read`**
```json
{
  "path": "/hr-docs/file.pdf"
}
```

**`POST /tools/files/write`**
```json
{
  "path": "/hr-docs/file.pdf",
  "content": "File content"
}
```

## Policy Configuration

Policies are stored in `backend/policies/*.yaml` and auto-reload on changes.

### Example Policy

```yaml
version: 1
agents:
  - id: finance-agent
    allow:
      - tool: payments
        actions: [create, refund]
        conditions:
          max_amount: 5000
          currencies: [USD, EUR]
  
  - id: hr-agent
    allow:
      - tool: files
        actions: [read]
        conditions:
          folder_prefix: "/hr-docs/"
```

### Supported Conditions

- `max_amount`: Maximum payment amount
- `currencies`: Allowed currency list
- `folder_prefix`: Required path prefix for files

### Hot-Reload Demo

1. Start the gateway: `docker-compose up --build`
2. Run a test: `curl -H "X-Agent-ID: finance-agent" -X POST localhost:8080/tools/payments/create -d '{"amount":1000,"currency":"USD","vendor_id":"V99"}'`
3. Edit `backend/policies/finance-agent.yaml` (e.g., change `max_amount: 5000` to `max_amount: 500`)
4. Re-run the same test - it should now be blocked
5. Check logs: `docker-compose logs aegis-gateway | grep "Policy"`

## Demo Scenarios

The demo script (`backend/scripts/demo.sh`) shows:

1. **Blocked high-value payment** (exceeds max_amount)
2. **Allowed payment** (within limits)
3. **Allowed HR file read** (inside `/hr-docs/`)
4. **Blocked HR file read** (outside `/hr-docs/`)
5. **Blocked currency** (not in allowed list)

## Observability

### Structured Logs

JSON logs are written to:
- `stdout` (visible in `docker-compose logs`)
- `backend/logs/aegis.log`

Log fields include:
- `agent.id`, `tool.name`, `tool.action`
- `decision.allow` (boolean)
- `policy.version`, `params.hash` (SHA-256)
- `latency.ms`, `trace.id`

### Tracing

OpenTelemetry spans are exported to Jaeger:
- **Jaeger UI**: http://localhost:16686
- Search for service: `aegis-gateway`
- Spans include policy decisions and tool calls

## Development

### Local Development

```bash
cd backend
pip install -r requirements.txt
export PYTHONPATH=$PWD
export POLICY_DIR=$PWD/policies
export LOGS_DIR=$PWD/logs
uvicorn app.main:app --reload --port 8080
```

### Project Structure

```
/project-argus
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── gateway.py           # Main proxy endpoint
│   │   ├── policy/              # Policy engine
│   │   │   ├── models.py        # Pydantic models
│   │   │   └── loader.py        # Hot-reload engine
│   │   ├── adapters/            # Mock tools
│   │   │   ├── payments.py      # Payment adapter
│   │   │   └── files.py         # File adapter
│   │   └── telemetry/           # OTel setup
│   │       └── setup.py
│   ├── policies/                # Policy files
│   │   ├── finance-agent.yaml
│   │   └── hr-agent.yaml
│   ├── scripts/
│   │   └── demo.sh              # Demo script
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml           # Full stack
├── otel-collector-config.yaml  # OTel config
└── README.md
```

## Security Features

- **Input Validation**: JSON schema validation via Pydantic
- **Parameter Hashing**: SHA-256 hashing of request bodies (no PII in logs)
- **Sanitized Errors**: Generic error messages to prevent information leakage
- **Policy Isolation**: Thread-safe policy reloading

## Extending

### Adding New Tools

1. Create adapter in `app/adapters/new_tool.py`
2. Add to `ADAPTERS` dict in `app/gateway.py`
3. Add policy conditions in `app/policy/models.py` if needed

### Adding New Conditions

1. Add field to `PolicyConditions` in `app/policy/models.py`
2. Implement evaluation logic in `PolicyConditions.evaluate()`

### Real Tool Integration

Replace mock adapters with HTTP clients or SDK calls to real services.

## Troubleshooting

### Common Issues

**Gateway not starting:**
- Check `docker-compose logs aegis-gateway`
- Ensure policies directory exists and contains valid YAML

**Policy not reloading:**
- Check file permissions on `backend/policies/`
- Look for policy validation errors in logs

**Tracing not working:**
- Verify OTel collector is running: `docker-compose ps`
- Check Jaeger UI: http://localhost:16686

### Logs

```bash
# Gateway logs
docker-compose logs -f aegis-gateway

# All services
docker-compose logs -f

# Policy reload events
docker-compose logs aegis-gateway | grep "Policy"
```

## ✅ Bonus Features Implemented

### 🔗 Call-Chain Awareness
- **X-Parent-Agent Header**: Track agent call chains for audit and policy enforcement
- **Ancestry-Based Rules**: Policy conditions based on call chain depth and ancestor requirements
- **Forbidden Ancestors**: Block calls from specific upstream agents (`forbidden_ancestors`)
- **Required Ancestors**: Enforce calls must come through specific supervisory agents (`required_ancestors`)
- **Chain Depth Limits**: Prevent deep call chains with `max_chain_depth`

### 🛡️ Approval Gates
- **Pending Approval Flow**: High-risk actions return `202 Accepted` with approval ID
- **Manual Approval Endpoint**: `POST /approve/{approval_id}` to approve pending actions
- **Expiring Approvals**: 24-hour expiry on pending approval requests
- **Audit Trail**: Full logging of approval workflows with approver tracking

### 🌐 Admin UI (Next.js 15 + TypeScript + Tailwind CSS 4)
- **Real-time Dashboard**: Live view of agents, policies, and decisions at **http://localhost:3000**
- **Policy Monitoring**: View current policy version and configuration
- **Decision History**: Last 50 policy decisions with real-time updates
- **Agent Overview**: All registered agents and their activity
- **Auto-refresh**: Updates every 5 seconds for real-time monitoring
- **Modern Stack**: Built with Next.js 15, TypeScript, and Tailwind CSS 4

### 📋 Enhanced Policy Features

```yaml
# Example: Call-chain aware policy
agents:
  - id: restricted-agent
    allow:
      - tool: files
        actions: [read]
        conditions:
          folder_prefix: "/public/"
          required_ancestors: [supervisor-agent]  # Must be called through supervisor
          max_chain_depth: 3                      # Limit call chain depth
          forbidden_ancestors: [malicious-agent]  # Block specific ancestors

  - id: finance-agent-high-value
    allow:
      - tool: payments
        actions: [create]
        requires_approval: true  # Requires manual approval
        conditions:
          max_amount: 50000
          currencies: [USD, EUR]
```

### 🚀 Enhanced Demo Scripts

Run the enhanced demo to see all features:
```bash
./backend/scripts/enhanced-demo.sh
```

This demonstrates:
- Call-chain enforcement with `X-Parent-Agent`
- Approval gates for high-value transactions
- Admin API endpoints
- Real-time decision tracking

## Production Considerations

- Replace in-memory stores with persistent databases
- Add authentication/authorization for the gateway itself
- Implement rate limiting and circuit breakers
- Use proper secret management for OTel endpoints
- Add health checks and monitoring alerts
- Consider policy versioning and rollback mechanisms
