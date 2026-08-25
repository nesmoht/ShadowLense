data "azurerm_client_config" "current" {}

locals {
  rg_name       = "rg-${var.workload}-${var.environment}-${var.region_suffix}-${var.instance}"
  storage_name  = "st${var.workload}${var.environment}${var.instance}"
  kv_name       = "kv-${var.workload}-${var.environment}-${var.region_suffix}"
  acr_name      = "acr${var.workload}${var.environment}${var.instance}"
  law_name      = "log-${var.workload}-${var.environment}-${var.region_suffix}-${var.instance}"
  cae_name      = "cae-${var.workload}-${var.environment}-${var.region_suffix}-${var.instance}"
  job_name      = "caj-${var.workload}-pipeline-${var.environment}"
  identity_name = "id-${var.workload}-${var.environment}-${var.region_suffix}-${var.instance}"
  ag_name       = "ag-${var.workload}-${var.environment}"

  common_tags = merge({
    environment = var.environment
    workload    = var.workload
    managed-by  = "terraform"
  }, var.tags)
}

resource "azurerm_resource_group" "this" {
  name     = local.rg_name
  location = var.location
  tags     = local.common_tags
}

# ── Identity ──────────────────────────────────────────────────────────
# Container Apps Job runs as this identity: pulls the image from ACR,
# reads secrets straight from Key Vault, and reads/writes the data share.
resource "azurerm_user_assigned_identity" "job" {
  name                = local.identity_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.common_tags
}

# ── Storage: Bronze/Silver/Gold Parquet + DuckDB file, mounted into the job ──
resource "azurerm_storage_account" "this" {
  name                            = local.storage_name
  resource_group_name             = azurerm_resource_group.this.name
  location                        = azurerm_resource_group.this.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

resource "azurerm_storage_share" "data" {
  name               = "pipeline-data"
  storage_account_id = azurerm_storage_account.this.id
  quota              = 20
}

resource "azurerm_role_assignment" "job_storage" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage File Data SMB Share Contributor"
  principal_id         = azurerm_user_assigned_identity.job.principal_id
}

# ── Key Vault: ANTHROPIC_API_KEY, SENDGRID_API_KEY ─────────────────────
resource "azurerm_key_vault" "this" {
  name                          = local.kv_name
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  soft_delete_retention_days    = 90
  purge_protection_enabled      = true
  public_network_access_enabled = true
  enable_rbac_authorization     = true

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = local.common_tags
}

resource "azurerm_role_assignment" "job_kv_secrets" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.job.principal_id
}

# Deployer needs write access to seed the two secrets below.
resource "azurerm_role_assignment" "deployer_kv_secrets" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "anthropic-api-key"
  value        = var.anthropic_api_key
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets]
}

resource "azurerm_key_vault_secret" "sendgrid_api_key" {
  name         = "sendgrid-api-key"
  value        = var.sendgrid_api_key
  key_vault_id = azurerm_key_vault.this.id
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets]
}

# ── Container Registry: holds the image CI builds on each push ─────────
resource "azurerm_container_registry" "this" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.common_tags
}

resource "azurerm_role_assignment" "job_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.job.principal_id
}

# ── CI identity: GitHub Actions pushes images via OIDC, no stored secret ──
resource "azuread_application" "ci" {
  display_name = "gha-${var.workload}-${var.github_repo}-${var.environment}"
}

resource "azuread_service_principal" "ci" {
  client_id = azuread_application.ci.client_id
}

resource "azuread_application_federated_identity_credential" "ci" {
  application_id = azuread_application.ci.id
  display_name   = "${var.github_repo}-main-push"
  subject        = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
}

resource "azurerm_role_assignment" "ci_acr_push" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.ci.object_id
}

# ── Container Apps environment + job ────────────────────────────────────
resource "azurerm_log_analytics_workspace" "this" {
  name                = local.law_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.common_tags
}

resource "azurerm_container_app_environment" "this" {
  name                       = local.cae_name
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = local.common_tags
}

resource "azurerm_container_app_environment_storage" "data" {
  name                         = "pipeline-data"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.this.name
  share_name                   = azurerm_storage_share.data.name
  access_key                   = azurerm_storage_account.this.primary_access_key
  access_mode                  = "ReadWrite"
}

resource "azurerm_container_app_job" "pipeline" {
  name                         = local.job_name
  location                     = azurerm_resource_group.this.location
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id

  replica_timeout_in_seconds = 3600
  replica_retry_limit        = 1

  schedule_trigger_config {
    cron_expression          = var.cron_schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.job.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.job.id
  }

  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.anthropic_api_key.id
    identity            = azurerm_user_assigned_identity.job.id
  }

  secret {
    name                = "sendgrid-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.sendgrid_api_key.id
    identity            = azurerm_user_assigned_identity.job.id
  }

  template {
    container {
      name   = "pipeline"
      image  = var.container_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
      env {
        name        = "SENDGRID_API_KEY"
        secret_name = "sendgrid-api-key"
      }
      env {
        name  = "DATA_DIR"
        value = "/app/data"
      }
      env {
        name  = "ALERT_FROM_EMAIL"
        value = "alerts@shadowlense.dev"
      }

      volume_mounts {
        name = "data"
        path = "/app/data"
      }
    }

    volume {
      name         = "data"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.data.name
    }
  }

  tags = local.common_tags
}

# ── Alerting: previous GitHub Actions schedule failed silently for a
# month before anyone noticed. Fire an email the first time a run fails. ──
resource "azurerm_monitor_action_group" "this" {
  name                = local.ag_name
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "shadowlens"

  email_receiver {
    name          = "owner"
    email_address = var.alert_email
  }

  tags = local.common_tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "job_failed" {
  name                = "alert-${var.workload}-job-failed-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  evaluation_frequency = "PT1H"
  window_duration      = "PT1H"
  scopes               = [azurerm_log_analytics_workspace.this.id]
  severity             = 1

  criteria {
    query                   = <<-KQL
      ContainerAppSystemLogs_CL
      | where EnvironmentName_s == "${local.cae_name}"
      | where Log_s has "Failed"
    KQL
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }

  tags = local.common_tags
}
