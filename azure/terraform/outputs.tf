output "foundry_project_id" {
  value = azurerm_cognitive_account_project.foundry_project.id
}

output "project_endpoint" {
  value       = "https://${var.hub_account_name}.services.ai.azure.com/api/projects/${var.project_name}"
  description = "Use as FOUNDRY_PROJECT_ENDPOINT for deploys and smoke tests."
}

output "model_deployment_name" {
  value = azurerm_cognitive_deployment.chat_model.name
}

output "function_app_name" {
  value = azurerm_linux_function_app.agent_api.name
}

output "function_app_hostname" {
  value = azurerm_linux_function_app.agent_api.default_hostname
}
