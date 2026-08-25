# Bootstrap once before first `terraform init` (state storage doesn't manage itself):
#
#   az group create -n rg-tfstate-shd -l swedencentral
#   az storage account create -n sttfstateshd001 -g rg-tfstate-shd -l swedencentral --sku Standard_LRS
#   az storage container create -n shadowlense --account-name sttfstateshd001

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-shd"
    storage_account_name = "sttfstateshd001"
    container_name       = "shadowlense"
    key                  = "shadowlense-prd.terraform.tfstate"
  }
}
