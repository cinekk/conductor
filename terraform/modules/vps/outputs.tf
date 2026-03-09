output "ip_address" {
  description = "Public IPv4 address of the provisioned server"
  value = (
    var.cloud_provider == "hetzner"
    ? (length(hcloud_server.conductor) > 0 ? hcloud_server.conductor[0].ipv4_address : "")
    : (length(digitalocean_droplet.conductor) > 0 ? digitalocean_droplet.conductor[0].ipv4_address : "")
  )
}

output "id" {
  description = "Provider-specific resource ID of the server"
  value = (
    var.cloud_provider == "hetzner"
    ? (length(hcloud_server.conductor) > 0 ? tostring(hcloud_server.conductor[0].id) : "")
    : (length(digitalocean_droplet.conductor) > 0 ? tostring(digitalocean_droplet.conductor[0].id) : "")
  )
}
