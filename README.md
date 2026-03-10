# Conductor

Personal AI orchestration framework. Conductor receives events from external tools (Linear, Telegram, …), routes each task to the right Claude agent, and posts results back — fully automated.

```
Linear webhook → Conductor → Orchestrator → Developer / QA / Deployer agent → Linear comment
```

Traces every LLM call to Langfuse for cost and latency visibility.

---

## Table of contents

1. [Architecture](#architecture)
2. [Local development](#local-development)
3. [Deployment](#deployment)
   - [Provision a VPS with Terraform](#1-provision-a-vps-with-terraform)
   - [Point DNS](#2-point-dns)
   - [Configure secrets](#3-configure-secrets)
   - [Deploy the stack](#4-deploy-the-stack)
   - [Switching cloud providers](#switching-cloud-providers)
4. [Observability](#observability)
5. [Project structure](#project-structure)

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  VPS  (Hetzner CX22 or DigitalOcean s-2vcpu-4gb)        │
│                                                          │
│  Caddy (ports 80/443, auto-HTTPS)                        │
│    conductor.yourdomain.com  →  conductor:8000           │
│    langfuse.yourdomain.com   →  langfuse:3000            │
│                                                          │
│  Docker Compose                                          │
│    conductor  — FastAPI + Claude Agent SDK               │
│    langfuse   — LLM observability UI                     │
│    postgres   — Langfuse database                        │
└──────────────────────────────────────────────────────────┘
```

Hexagonal design: the core domain has zero external dependencies. All I/O (Linear API, Claude SDK, Langfuse OTLP) lives in swappable adapters.

---

## Local development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- Python 3.14 (installed automatically by uv)
- `ANTHROPIC_API_KEY` in your environment

### Setup

```bash
git clone https://github.com/yourusername/conductor.git
cd conductor
uv sync                  # creates .venv and installs all deps
cp .env.example .env     # fill in your API keys
```

### Run

```bash
make dev                 # starts on http://localhost:8000
curl localhost:8000/health   # → {"status":"ok"}
```

To enable Linear webhook processing locally:

```bash
# Set LINEAR_API_KEY, LINEAR_TEAM_ID, LINEAR_WEBHOOK_SECRET in .env, then:
make dev-linear

# Expose to the internet for webhook delivery:
ngrok http 8000
# Paste the ngrok URL as the webhook endpoint in Linear → Settings → API → Webhooks
```

### Test

```bash
make test         # runs all 61 tests
make lint         # ruff check + format check
make typecheck    # mypy --strict
make fmt          # auto-fix formatting
```

---

## Deployment

The full stack (Conductor + Langfuse + Postgres + Caddy) is provisioned with Terraform and deployed via Docker Compose. HTTPS certificates are issued automatically by Caddy via Let's Encrypt.

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.6
- An SSH key uploaded to your cloud provider
- A domain with DNS you can manage

### 1. Provision a VPS with Terraform

```bash
# One-time init
make tf-init

# Copy the example and fill in your values
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
$EDITOR terraform/terraform.tfvars
```

`terraform.tfvars` — minimum required fields:

```hcl
cloud_provider   = "hetzner"          # or "digitalocean"
hcloud_token     = "your-api-token"   # Hetzner Cloud → API tokens
ssh_key_name     = "my-key"           # must already exist in the provider
github_repo      = "yourusername/conductor"
conductor_domain = "conductor.yourdomain.com"
langfuse_domain  = "langfuse.yourdomain.com"
```

```bash
make tf-plan    # review what will be created
make tf-apply   # provision the VPS (~30 seconds)
```

Terraform prints the server IP and next steps when it finishes:

```
server_ip = "1.2.3.4"
ssh_command = "ssh root@1.2.3.4"
next_steps = ...
```

### 2. Point DNS

Create two A records pointing at the server IP:

| Hostname | Type | Value |
|---|---|---|
| `conductor.yourdomain.com` | A | `1.2.3.4` |
| `langfuse.yourdomain.com` | A | `1.2.3.4` |

Caddy will automatically obtain TLS certificates once DNS propagates.

### 3. Configure secrets

```bash
cp .env.example .env
$EDITOR .env   # fill in all values (API keys, domain names, Langfuse secrets)

# Copy the file to the server
make deploy-env SERVER_IP=1.2.3.4
```

Key variables to set in `.env`:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `LINEAR_API_KEY` | Linear API token |
| `LINEAR_WEBHOOK_SECRET` | From Linear → Settings → Webhooks |
| `LINEAR_TEAM_ID` | Your Linear team UUID |
| `CONDUCTOR_DOMAIN` | e.g. `conductor.yourdomain.com` |
| `LANGFUSE_DOMAIN` | e.g. `langfuse.yourdomain.com` |
| `LANGFUSE_DB_PASSWORD` | Any strong random string |
| `LANGFUSE_NEXTAUTH_SECRET` | `openssl rand -hex 32` |
| `LANGFUSE_SALT` | `openssl rand -hex 32` |

### 4. Deploy the stack

```bash
make deploy SERVER_IP=1.2.3.4
```

This SSHs into the server, pulls the latest code, pulls Docker images, and restarts containers with zero downtime (`docker compose up -d --remove-orphans`).

To get the IP from Terraform state without looking it up manually:

```bash
make deploy SERVER_IP=$(make tf-output)
```

**Verify:**

```bash
curl https://conductor.yourdomain.com/health  # → {"status":"ok"}
# Open https://langfuse.yourdomain.com → create an account on first visit
```

### Switching cloud providers

The Terraform module supports Hetzner and DigitalOcean out of the box. To switch:

```hcl
# terraform.tfvars
cloud_provider = "digitalocean"
do_token       = "your-do-api-token"
# hcloud_token can be removed or left empty
```

```bash
make tf-plan   # verify — Hetzner resources will be destroyed, DO created
make tf-apply
```

The VPS module interface (`modules/vps/`) is provider-agnostic. Adding a new provider (Linode, Vultr, …) means adding a new `<provider>.tf` file in the module with `count = var.cloud_provider == "<name>" ? 1 : 0`.

---

## Observability

Every LLM call is traced to Langfuse via OpenTelemetry (OTLP). After deploying:

1. Open `https://langfuse.yourdomain.com` and create an account
2. Go to **Settings → API Keys** → create a key pair
3. Add to `.env`:
   ```
   LANGFUSE_HOST=https://langfuse.yourdomain.com
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
4. Re-deploy: `make deploy SERVER_IP=...`

Each task processed by Conductor produces:
- A `task.handle` parent span with task ID, source, and agent type
- An `agent.execute:<type>` child span with result status
- An `llm.run` grandchild span with cost (USD), token usage, and latency

To use a different OTLP backend instead of Langfuse:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-backend:4318
```

---

## Project structure

```
conductor/
├── core/
│   ├── domain/task.py        # ConductorTask, TaskStatus, AgentType
│   ├── orchestrator.py       # routes task status → agent type
│   └── ports/                # ABCs: AgentPort, AdapterPort, LLMPort
├── adapters/
│   ├── agents/claude_agent.py    # ClaudeAgentAdapter (real) + MockLLMAdapter (tests)
│   └── linear/
│       ├── client.py         # GraphQL wrapper for Linear API
│       ├── adapter.py        # AdapterPort: Linear webhook → ConductorTask → comment
│       └── signature.py      # HMAC-SHA256 webhook verification
├── api/webhook.py            # FastAPI: POST /webhook/{source}, GET /health
├── observability.py          # OTEL setup, get_tracer()
├── prompts.py                # File-based prompt registry (name@version.txt)
├── prompt_templates/         # developer-agent@1.txt, qa-agent@1.txt
├── config.py                 # pydantic-settings from env vars
└── main.py                   # build_app() wires everything together

terraform/
├── main.tf / variables.tf / outputs.tf
├── cloud-init.yml.tpl        # first-boot provisioning script
└── modules/vps/
    ├── hetzner.tf            # Hetzner CX22 + firewall
    └── digitalocean.tf       # DigitalOcean droplet + firewall

Dockerfile                    # python:3.14-slim + uv
docker-compose.yml            # full production stack
Caddyfile                     # reverse proxy + auto-HTTPS
```
