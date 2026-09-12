param location string = 'eastus'
param foundryName string = 'my-foundry-resource'
param projectName string = 'agent-lab'
param modelName string = 'gpt-5-mini'
param modelVersion string = '2025-08-07'

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  name: projectName
  parent: aiFoundry
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {}
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: modelName
  sku: { capacity: 1, name: 'GlobalStandard' }
  properties: {
    model: { name: modelName, format: 'OpenAI', version: modelVersion }
  }
}

output projectId string = aiProject.id
output projectEndpoint string = 'https://${foundryName}.services.ai.azure.com/api/projects/${projectName}'
output deploymentName string = modelName
