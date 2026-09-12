# Terraform (a2a-prototype)

Manages, in the existing `my-foundry-rg`:

- `azurerm_cognitive_account_project.agent-lab` - Foundry project under the
  existing classic S0 hub account (`my-foundry-resource`, referenced via data
  source, never recreated).
- `azurerm_cognitive_deployment.gpt-5-mini` - chat model, GlobalStandard
  capacity 1 (per-token billing only).
- Function app `a2a-agent-api` + its storage account on a Y1 Consumption plan
  in **centralus** - $0 when idle. Quota is region-bound: eastus Y1 quota is 0
  on this subscription, centralus works (verified with a live probe). Function
  apps are NOT supported on F1/Free plans, so the existing F1 plan is not an
  option.

## First-run bootstrap (one-time imports)

The project and model were initially provisioned by
`azure/foundry/main.bicep` (kept as a fallback). Import them so Terraform
adopts rather than recreates:

```bash
SUB=3ef6aa8d-0594-4998-883f-9d5cc4953ee2
cd azure/terraform
terraform init
terraform import azurerm_cognitive_account_project.foundry_project \
  "/subscriptions/$SUB/resourceGroups/my-foundry-rg/providers/Microsoft.CognitiveServices/accounts/my-foundry-resource/projects/agent-lab"
terraform import azurerm_cognitive_deployment.chat_model \
  "/subscriptions/$SUB/resourceGroups/my-foundry-rg/providers/Microsoft.CognitiveServices/accounts/my-foundry-resource/deployments/gpt-5-mini"
terraform plan   # expect: No changes
```

## Day-2 usage

```bash
terraform init
terraform plan
terraform apply      # e.g. bump model_version, add env settings
terraform destroy    # removes ONLY resources this config created
```

Auth: `az login` (or `ARM_SUBSCRIPTION_ID` + federated creds in CI).
