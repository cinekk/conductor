# ── DigitalOcean resources ─────────────────────────────────────────────────────
# Active when: cloud_provider = "digitalocean"
# Droplet: s-2vcpu-4gb — 2 vCPU, 4 GB RAM, 80 GB SSD, ~$24/mo (Frankfurt)
#
# To switch: terraform apply -var="cloud_provider=digitalocean" -var="do_token=<token>"

data "digitalocean_ssh_key" "conductor" {
  count = var.cloud_provider == "digitalocean" ? 1 : 0
  name  = var.ssh_key_name
}

resource "digitalocean_droplet" "conductor" {
  count     = var.cloud_provider == "digitalocean" ? 1 : 0
  name      = var.name
  image     = "ubuntu-24-04-x64"
  size      = "s-2vcpu-4gb"
  region    = "fra1" # Frankfurt
  ssh_keys  = [data.digitalocean_ssh_key.conductor[0].fingerprint]
  user_data = var.user_data

  lifecycle {
    ignore_changes = [user_data]
  }
}

resource "digitalocean_firewall" "conductor" {
  count   = var.cloud_provider == "digitalocean" ? 1 : 0
  name    = "${var.name}-fw"
  droplet_ids = [digitalocean_droplet.conductor[0].id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
