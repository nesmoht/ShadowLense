variable "workload" {
  type        = string
  description = "Short workload name used in resource naming."
  default     = "shadowlense"
}

variable "environment" {
  type        = string
  description = "Deployment environment."
  default     = "prd"

  validation {
    condition     = contains(["prd", "dev", "tst", "stg"], var.environment)
    error_message = "environment must be one of: prd, dev, tst, stg."
  }
}

variable "location" {
  type        = string
  description = "Azure region for all resources."
  default     = "swedencentral"
}

variable "region_suffix" {
  type        = string
  description = "Short region code used in resource naming."
  default     = "sdc"
}

variable "instance" {
  type        = string
  description = "Instance suffix for resource naming."
  default     = "001"
}

variable "cron_schedule" {
  type        = string
  description = "Cron expression controlling how often the pipeline job runs (Container Apps job scheduled trigger, UTC)."
  default     = "0 */6 * * *"
}

variable "container_image" {
  type        = string
  description = "Full image reference (registry/repo:tag) the job runs. Updated by CI on each build."
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "alert_email" {
  type        = string
  description = "Email address notified when a pipeline job run fails."
}

variable "github_org" {
  type        = string
  description = "GitHub org/user that owns the repo, used for OIDC federated credential subject."
  default     = "nesmoht"
}

variable "github_repo" {
  type        = string
  description = "GitHub repository name, used for OIDC federated credential subject."
  default     = "ShadowLense"
}

variable "anthropic_api_key" {
  type        = string
  description = "Anthropic API key, seeded into Key Vault as a secret."
  sensitive   = true
}

variable "sendgrid_api_key" {
  type        = string
  description = "SendGrid API key, seeded into Key Vault as a secret."
  sensitive   = true
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Additional resource tags merged with the common tag set."
  default     = {}
}
