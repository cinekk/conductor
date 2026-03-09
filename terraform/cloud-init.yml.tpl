#cloud-config
# Runs once on first boot. Installs Docker, clones the repo, and sets up the
# stack ready for `make deploy` to copy secrets and start containers.

package_update: true
package_upgrade: true

packages:
  - apt-transport-https
  - ca-certificates
  - curl
  - gnupg
  - git

runcmd:
  # ── Docker ─────────────────────────────────────────────────────────────────
  - curl -fsSL https://get.docker.com | sh
  - systemctl enable --now docker

  # ── Clone repo ─────────────────────────────────────────────────────────────
  - git clone https://github.com/${github_repo}.git /opt/conductor

  # ── Write Caddyfile with real domains ─────────────────────────────────────
  - |
    cat > /opt/conductor/Caddyfile <<'CADDY'
    ${conductor_domain} {
        reverse_proxy conductor:8000
    }

    ${langfuse_domain} {
        reverse_proxy langfuse:3000
    }
    CADDY

  # ── Placeholder .env (secrets copied by `make deploy-env`) ────────────────
  - cp /opt/conductor/.env.example /opt/conductor/.env

  # Stack starts only after `make deploy-env` copies real secrets.
  # The Caddyfile is already correct — Caddy will auto-provision TLS certs
  # once DNS is pointed at this server.

final_message: |
  Conductor VPS is ready.
  Next:
    1. Point DNS: ${conductor_domain} and ${langfuse_domain} -> this server's IP
    2. Run: make deploy-env SERVER_IP=<this IP>
    3. Run: make deploy SERVER_IP=<this IP>
