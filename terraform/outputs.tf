output "server_ip" {
  description = "Public IPv4 address of the provisioned VPS"
  value       = module.vps.ip_address
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh root@${module.vps.ip_address}"
}

output "next_steps" {
  description = "What to do after provisioning"
  value       = <<-EOT
    1. Point DNS:
         ${var.conductor_domain}  →  ${module.vps.ip_address}
         ${var.langfuse_domain}   →  ${module.vps.ip_address}

    2. Copy secrets:
         make deploy-env SERVER_IP=${module.vps.ip_address}

    3. Start the stack:
         make deploy SERVER_IP=${module.vps.ip_address}
  EOT
}
