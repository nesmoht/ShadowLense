output "resource_group_name" {
  value       = azurerm_resource_group.this.name
  description = "Resource group containing all Shadowlense infrastructure."
}

output "container_registry_login_server" {
  value       = azurerm_container_registry.this.login_server
  description = "Push the pipeline image here; CI needs AcrPush on this registry."
}

output "container_app_job_name" {
  value       = azurerm_container_app_job.pipeline.name
  description = "Name of the scheduled Container Apps job running the pipeline."
}

output "key_vault_name" {
  value       = azurerm_key_vault.this.name
  description = "Key Vault holding ANTHROPIC_API_KEY and SENDGRID_API_KEY."
}

output "job_identity_client_id" {
  value       = azurerm_user_assigned_identity.job.client_id
  description = "Client ID of the managed identity the job runs as."
}

output "ci_client_id" {
  value       = azuread_application.ci.client_id
  description = "Set as AZURE_CLIENT_ID in the GitHub Actions workflow (OIDC, no secret needed)."
}

output "ci_tenant_id" {
  value       = data.azurerm_client_config.current.tenant_id
  description = "Set as AZURE_TENANT_ID in the GitHub Actions workflow."
}

output "subscription_id" {
  value       = data.azurerm_client_config.current.subscription_id
  description = "Set as AZURE_SUBSCRIPTION_ID in the GitHub Actions workflow."
}
