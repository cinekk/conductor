# ── Hetzner Cloud resources ────────────────────────────────────────────────────
# Active when: cloud_provider = "hetzner"
# Server: CX22 — 2 vCPU, 4 GB RAM, 40 GB SSD, ~€4.50/mo (Helsinki)

data "hcloud_ssh_key" "conductor" {
  count = var.cloud_provider == "hetzner" ? 1 : 0
  name  = var.ssh_key_name
}

resource "hcloud_server" "conductor" {
  count       = var.cloud_provider == "hetzner" ? 1 : 0
  name        = var.name
  image       = "ubuntu-24.04"
  server_type = "cx22"
  location    = "hel1" # Helsinki — closest to EU + cheapest
  ssh_keys    = [data.hcloud_ssh_key.conductor[0].id]
  user_data   = var.user_data

  lifecycle {
    ignore_changes = [user_data] # re-provisioning resets the server; handle via `make deploy`
  }
}

resource "hcloud_firewall" "conductor" {
  count = var.cloud_provider == "hetzner" ? 1 : 0
  name  = "${var.name}-fw"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_firewall_attachment" "conductor" {
  count       = var.cloud_provider == "hetzner" ? 1 : 0
  firewall_id = hcloud_firewall.conductor[0].id
  server_ids  = [hcloud_server.conductor[0].id]
}
