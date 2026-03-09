.PHONY: dev dev-linear test lint typecheck fmt \
        deploy deploy-env tf-init tf-plan tf-apply tf-destroy

# ─── Development ──────────────────────────────────────────────────────────────

dev:
	uv run uvicorn conductor.main:app --reload --host 0.0.0.0 --port 8000

dev-linear:
	@test -n "$$LINEAR_API_KEY" || (echo "Set LINEAR_API_KEY, LINEAR_TEAM_ID, LINEAR_WEBHOOK_SECRET first" && exit 1)
	uv run uvicorn conductor.main:app --reload --host 0.0.0.0 --port 8000

# ─── Quality ──────────────────────────────────────────────────────────────────

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy conductor/

fmt:
	uv run ruff format .
	uv run ruff check --fix .

# ─── Deployment ───────────────────────────────────────────────────────────────
# Usage:
#   make deploy SERVER_IP=1.2.3.4
#   make deploy-env SERVER_IP=1.2.3.4   # copies .env first
#
# SERVER_IP can also come from Terraform state:
#   export SERVER_IP=$$(make tf-output)

SERVER_IP ?=
_require_server_ip:
	@test -n "$(SERVER_IP)" || (echo "Set SERVER_IP=<ip>  (run 'make tf-output' after tf-apply)" && exit 1)

deploy-env: _require_server_ip
	@echo "→ Copying .env to $(SERVER_IP)..."
	scp .env root@$(SERVER_IP):/opt/conductor/.env

deploy: _require_server_ip
	@echo "→ Deploying to $(SERVER_IP)..."
	ssh root@$(SERVER_IP) \
	  "cd /opt/conductor && git pull && docker compose pull && docker compose up -d --remove-orphans"

tf-output:
	@terraform -chdir=terraform output -raw server_ip

# ─── Terraform ────────────────────────────────────────────────────────────────

tf-init:
	terraform -chdir=terraform init

tf-plan:
	terraform -chdir=terraform plan

tf-apply:
	terraform -chdir=terraform apply

tf-destroy:
	terraform -chdir=terraform destroy
