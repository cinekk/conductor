variable "cloud_provider" {
  description = "Which provider to create resources in: hetzner | digitalocean"
  type        = string
}

variable "name" {
  description = "Name tag for the server and associated resources"
  type        = string
}

variable "ssh_key_name" {
  description = "Name of the SSH key already registered with the cloud provider"
  type        = string
}

variable "user_data" {
  description = "cloud-init user-data script to run on first boot"
  type        = string
}
