# Foundry project under the existing hub (created agent-lab in eastus).
# NOTE: this resource type maps to Microsoft.CognitiveServices/accounts/projects
# (classic hub). azurerm_ai_foundry_project would require a
# MachineLearningServices-based AI Services hub, which we do not use.
resource "azurerm_cognitive_account_project" "foundry_project" {
  name                 = var.project_name
  location             = var.location
  cognitive_account_id = data.azurerm_cognitive_account.hub.id
  tags                 = local.common_tags

  identity {
    type = "SystemAssigned"
  }
}

# One chat model at minimum capacity. Deployments are free until invoked;
# tokens are billed per use (gpt-5-mini @ capacity 1 is tiny).
resource "azurerm_cognitive_deployment" "chat_model" {
  name                 = var.model_name
  cognitive_account_id = data.azurerm_cognitive_account.hub.id
  rai_policy_name      = "Microsoft.DefaultV2"

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }

  sku {
    name     = var.model_sku
    capacity = var.model_capacity
  }
}
