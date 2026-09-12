# Auth via az login (local) or ARM_* env vars / federated creds in CI.
# The subscription is picked up from ARM_SUBSCRIPTION_ID when set; otherwise
# from the logged-in `az account`. Pin it explicitly for CI if you prefer.
provider "azurerm" {
  features {}
}
