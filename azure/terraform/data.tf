# The classic AIServices (Foundry) hub account already exists - reference it,
# never manage it. Everything here is created *under* it or alongside it.
data "azurerm_cognitive_account" "hub" {
  name                = var.hub_account_name
  resource_group_name = var.hub_resource_group
}
