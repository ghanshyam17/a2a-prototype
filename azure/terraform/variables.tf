variable "location" {
  type        = string
  default     = "eastus"
  description = "Azure region for all resources."
}

variable "hub_resource_group" {
  type        = string
  default     = "my-foundry-rg"
  description = "Existing RG that holds the (classic, S0) Foundry account."
}

variable "hub_account_name" {
  type        = string
  default     = "my-foundry-resource"
  description = "Existing classic AIServices (Foundry) account. Referenced, never recreated."
}

variable "project_name" {
  type        = string
  default     = "agent-lab"
  description = "Foundry project (child of the hub account)."
}

variable "model_name" {
  type        = string
  default     = "gpt-5-mini"
  description = "Chat model deployment for the hosted agents (GA on this subscription)."
}

variable "model_version" {
  type        = string
  default     = "2025-08-07"
  description = "Model version to deploy."
}

variable "model_sku" {
  type        = string
  default     = "GlobalStandard"
  description = "Deployment SKU (GlobalStandard honors quota, capacity 1 ~= 1K tok/min)."
}

variable "model_capacity" {
  type        = number
  default     = 10
  description = "Deployment capacity (keep at 1 for rare-call workloads)."
}

variable "func_location" {
  type        = string
  default     = "centralus"
  description = "Function plan region. centralus has Y1 (Consumption) quota on this subscription; eastus does not (0 Y1 VMs)."
}

variable "func_prefix" {
  type        = string
  default     = "a2a"
  description = "Name prefix for the Function app + its storage account."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Extra tags merged onto every managed resource."
}

locals {
  # Shared resources (project + model) carry IDENTICAL tags in all three
  # stacks so concurrent applies never fight over tag values.
  shared_tags = {
    project      = "agent-lab"
    repo         = "shared"
    owner        = "ghanshyam17"
    environment  = "learning"
    managed-by   = "terraform"
    cost-posture = "zero-idle"
  }
  common_tags = merge(
    {
      project      = "a2a-prototype"
      repo         = "github.com/ghanshyam17/a2a-prototype"
      owner        = "ghanshyam17"
      environment  = "learning"
      managed-by   = "terraform"
      cost-posture = "zero-idle"
    },
    var.tags,
  )
}
