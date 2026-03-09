# ─── Provider selection ────────────────────────────────────────────────────────

variable "cloud_provider" {
  description = "Cloud provider to use. Switch with: terraform apply -var='cloud_provider=digitalocean'"
  type        = string
  default     = "hetzner"

  validation {
    condition     = contains(["hetzner", "digitalocean"], var.cloud_provider)
    error_message = "cloud_provider must be 'hetzner' or 'digitalocean'."
  }
}

# ─── API tokens (set only the one you need) ────────────────────────────────────

variable "hcloud_token" {
  description = "Hetzner Cloud API token (required when cloud_provider = 'hetzner')"
  type        = string
  sensitive   = true
  default     = ""
}

variable "do_token" {
  description = "DigitalOcean API token (required when cloud_provider = 'digitalocean')"
  type        = string
  sensitive   = true
  default     = ""
}

# ─── Server config ─────────────────────────────────────────────────────────────

variable "server_name" {
  description = "Name tag for the VPS"
  type        = string
  default     = "conductor"
}

variable "ssh_key_name" {
  description = "Name of the SSH key already uploaded to the cloud provider"
  type        = string
}

variable "github_repo" {
  description = "GitHub repo to clone on the VPS (e.g. yourusername/conductor)"
  type        = string
}

# ─── Domains ───────────────────────────────────────────────────────────────────

variable "conductor_domain" {
  description = "Public domain for Conductor webhooks (e.g. conductor.yourdomain.com)"
  type        = string
}

variable "langfuse_domain" {
  description = "Public domain for the Langfuse UI (e.g. langfuse.yourdomain.com)"
  type        = string
}
