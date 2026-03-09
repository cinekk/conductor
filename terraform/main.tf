terraform {
  required_version = ">= 1.6"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.39"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

provider "digitalocean" {
  token = var.do_token
}

locals {
  user_data = templatefile("${path.module}/cloud-init.yml.tpl", {
    github_repo      = var.github_repo
    conductor_domain = var.conductor_domain
    langfuse_domain  = var.langfuse_domain
  })
}

module "vps" {
  source = "./modules/vps"

  cloud_provider = var.cloud_provider
  name           = var.server_name
  ssh_key_name   = var.ssh_key_name
  user_data      = local.user_data
}
