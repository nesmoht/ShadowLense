# Shadowlense infrastructure

Single-environment (prd) Azure infrastructure for the pipeline. Deliberately
minimal — one Container Apps Job on a cron schedule, no VNet, no dev copy.

## What this deploys

- **Container Apps Job** (`azurerm_container_app_job.pipeline`) — runs `main.py`
  on `var.cron_schedule` (default every 6h), scales to zero between runs
- **Storage Account + Files share** — Bronze/Silver/Gold Parquet and the
  DuckDB file, mounted at `/app/data` in the job
- **Key Vault** — `ANTHROPIC_API_KEY`, `SENDGRID_API_KEY`, read by the job's
  managed identity at execution time (never touch GitHub secrets)
- **Container Registry (Basic)** — image built and pushed by
  `.github/workflows/build-image.yml`
- **Log Analytics + action group alert** — emails `var.alert_email` the first
  time a job execution fails. This is the piece that was missing before: the
  old GitHub Actions schedule failed silently for a month (pandas dependency,
  then exhausted Anthropic credit) before anyone noticed.

Frontend hosting is intentionally out of scope — the Next.js dashboard hasn't
been reviewed yet.

## First-time deploy

```bash
# 1. Bootstrap state storage (one-off, see backend.tf)
az group create -n rg-tfstate-shd -l swedencentral
az storage account create -n sttfstateshd001 -g rg-tfstate-shd -l swedencentral --sku Standard_LRS
az storage container create -n shadowlense --account-name sttfstateshd001

# 2. Init and apply — container_image defaults to a placeholder until CI has
#    pushed a real image once, so the first apply's job won't run correctly.
terraform init
terraform apply \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="alert_email=you@example.com"

# 3. Wire up GitHub Actions OIDC (no secret to store):
#    Repo → Settings → Environments/Variables → set as *repository variables*:
#      AZURE_CLIENT_ID       = terraform output -raw ci_client_id
#      AZURE_TENANT_ID       = terraform output -raw ci_tenant_id
#      AZURE_SUBSCRIPTION_ID = terraform output -raw subscription_id
#      ACR_NAME              = terraform output -raw container_registry_login_server (minus .azurecr.io)
#      ACR_LOGIN_SERVER      = terraform output -raw container_registry_login_server

# 4. Push to main (or run the workflow manually) to build+push the real image,
#    then re-apply with the real image reference if you changed the default:
terraform apply -var="container_image=<acr-login-server>/shadowlense-pipeline:latest" ...
```

The job always pulls the `:latest` tag fresh on each scheduled execution, so
once step 4 has run once, new pushes to `main` reach production on the next
cron tick without another `terraform apply`.

## Known gaps

- `sendgrid_api_key` defaults to `""` — alerts are effectively disabled until
  it's set; that mirrors the pipeline's existing "SendGrid key missing"
  startup warning.
- The failure alert's KQL query (`ContainerAppSystemLogs_CL`, `Log_s has
  "Failed"`) hasn't been validated against a real failed execution yet —
  confirm the schema once the first job run happens.
- Tor sources are still `use_tor: False` in `pipeline/config.py`; this
  infrastructure doesn't provision a Tor proxy sidecar.
