# Functionality -> Foundry platform mapping (a2a-prototype)

Every functional piece of this project mapped onto the Foundry platform
primitive that hosts it. Nothing runs on idle-billed infrastructure.

| Functionality (repo code) | Foundry platform capability | Where it lives |
|---|---|---|
| Pro/cons debate orchestration (`DebateOrchestrator`, LangGraph) | **Hosted agent** (`a2a-debate`) - own framework code, platform manages hosting/scaling/sessions | `azure/hosted-agent/` -> Agent Service |
| Chat surface (web SSE UI today) | **Responses protocol** - platform-managed conversation history, streaming, background mode; chat via playground or any OpenAI-compatible client | platform endpoint |
| Agent-to-agent HTTP protocol (`a2a_protocol/`) | **A2A protocol (preview)** on hosted agents: `{project}/agents/{name}/endpoint/protocols/a2a` - platform exposes the agent card + delegation endpoint | agent definition (`protocol_versions`) |
| Custom payload exchange (non-OpenAI) | **Invocations protocol** (can be added alongside Responses) | agent definition |
| Model-tier routing decision (`router/`) | **Model catalog deployments** - tier = which deployment serves the call (gpt-5-mini now; add a second deployment for the "higher" tier) | `terraform/foundry.tf` |
| Router tool in chat (`score_route`) | **Tool** inside the hosted agent (in-process) - can be promoted to a **Toolbox** tool later for cross-agent reuse | `main.py` tools |
| Memory stack (`memory/`: short/episodic/semantic/shared) | **Durable state store** (server-backed KV, survives idle eviction) for session state; **platform-managed conversation history** for chat turns; semantic search -> AI Search **connection** (Toolbox) when needed | next step: state store SDK |
| Route/observability events | **Built-in OpenTelemetry -> App Insights** (connection string auto-injected by the platform) | App Insights in the project |
| HTTP API for external callers | **Azure Functions** (Consumption, $0 idle) - callable by agents via **Toolbox OpenAPI tool** or plain HTTP | `azure/functions/` |
| Deterministic stub LLM (`MODEL_PROVIDER=stub`) | **Foundry model catalog** is the upgrade path - same code, `AzureAIOpenAIApiChatModel` points at the deployment | env-driven |

Cost posture: hosted agent sandboxes deprovision after idle timeout (billed
only for active session CPU/memory); model deployment is per-token; Functions
are per-execution. Idle subscription cost = $0.
