# Azure deployment (a2a-prototype)

Zero-idle-cost Azure footprint: the project lives in the **`agent-lab` Foundry
project** (free S0 `my-foundry-resource`, eastus) and only consumes compute when
somebody actually calls it.

## What gets deployed

| Piece | Azure service | Idle cost | Purpose |
|---|---|---|---|
| `hosted-agent/` | Foundry hosted agent (Agent Service) | $0 (sandbox deprovisioned after idle timeout, default 15 min) | Chat with the debate system (Responses protocol), tools call the real `DebateOrchestrator` |
| `functions/` | Function app on Consumption plan | $0 (billed per execution only) | HTTP surface: `POST /api/agent` (debate or route scoring) — the A2A-ish endpoint other systems can call |
| `foundry/main.bicep` | Foundry project + model deployment | $0 (deployment is free; tokens are billed per use) | `agent-lab` project + `gpt-5-mini` (GlobalStandard, capacity 1) |

No App Service plan, no VMs, no always-on containers.

## One-time setup

```bash
az login
# project + model (idempotent):
az deployment group create -g my-foundry-rg -f azure/foundry/main.bicep \
  -p foundryName=my-foundry-resource -p projectName=agent-lab \
  -p modelName=gpt-5-mini -p modelVersion=2025-08-07
```

## Deploy the hosted agent

```bash
python3 -m venv .venv-deploy && . .venv-deploy/bin/activate
pip install "azure-ai-projects>=2.3.0" azure-identity python-dotenv
export FOUNDRY_PROJECT_ENDPOINT=https://my-foundry-resource.services.ai.azure.com/api/projects/agent-lab
export FOUNDRY_MODEL_NAME=gpt-5-mini
python azure/deploy_hosted_agent.py
```

Then chat with it:

```bash
python azure/scripts/smoke.py --message "Debate: remote work makes teams stronger"
```

(First run of `smoke.py` performs the Entra device-code login; after that the
token is cached. Every request spawns a sandbox; after 15 idle minutes Azure
deprovisions it — that is the cost control.)

## Deploy the Function app

```bash
func azure funcapp publish <function-app-name>  # see azure/scripts/deploy-functions.sh
```

The function bundles the repo's `src/a2a` beside itself, so the deployed API
runs the same orchestrator as local dev. `MODEL_PROVIDER=stub` keeps it 100%
LLM-bill-free; set provider/model env vars to wire a real model.

## CI

`.github/workflows/ci.yml` syntax-checks every Python file under `azure/` on
each push that touches it. Deploys are intentionally **manual** (`workflow_dispatch`,
`azure/scripts/`) — an idle project must not accrue CI minutes either.
