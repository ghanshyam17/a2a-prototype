"""Foundry hosted agent for the a2a debate prototype (Responses protocol).

Runs on Foundry Agent Service via ``langchain_azure_ai`` ``ResponsesHostServer``
(same pattern as microsoft-foundry/foundry-samples). The graph is a plain
LangChain ``create_agent`` whose tools wrap the repo's real debate stack:

- ``run_debate``  - runs the actual ``DebateOrchestrator`` (pro/cons arguments,
  rebuttals, final summary) from the bundled ``a2a`` package.
- ``score_route`` - heuristic score + tier decision from the real
  ``AgenticRouterBridge`` (a2a/router/bridge.py).

The orchestrator's internal LLM stays ``MODEL_PROVIDER=stub`` unless provider
env vars are set - the hosted agent's own model call (gpt-5-mini via
``AzureAIOpenAIApiChatModel``) drives the conversation; tool results come from
the prototype code. Idle cost stays zero: Agent Service deprovisions the
sandbox after the idle timeout and bills only active session compute.

Import layout: the deploy zip bundles the repo's ``src/a2a`` under
``_vendor/a2a``; when running from a repo checkout the live tree is used.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _bootstrap_imports() -> None:
    """Make ``a2a`` importable in both the repo tree and the deploy zip."""
    here = Path(__file__).resolve().parent

    vendor = here / "_vendor"  # deploy zip layout: <root>/_vendor/a2a
    if (vendor / "a2a").is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))

    # Repo checkout layout: walk up to the dir containing src/a2a.
    for cand in (here, *here.parents):
        if (cand / "src" / "a2a").is_dir():
            src = cand / "src"
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            break


_bootstrap_imports()

from a2a.agents.llm import make_llm  # noqa: E402
from a2a.config import settings  # noqa: E402
from a2a.debate.orchestrator import DebateOrchestrator  # noqa: E402

_ORCH: DebateOrchestrator | None = None
_BRIDGE = None  # lazy: AgenticRouterBridge needs the vendored agentic_router


def _bridge():
    global _BRIDGE
    if _BRIDGE is None:
        try:
            from a2a.router import AgenticRouterBridge

            _BRIDGE = AgenticRouterBridge(
                lower_threshold=settings.router_lower_threshold,
                higher_threshold=settings.router_higher_threshold,
                classifier_band=settings.router_classifier_band,
            )
        except Exception as exc:  # noqa: BLE001 - vendored sibling missing
            logger.warning("router bridge unavailable: %s", exc)
    return _BRIDGE


def _orchestrator() -> DebateOrchestrator:
    global _ORCH
    if _ORCH is None:
        _ORCH = DebateOrchestrator(llm=make_llm())
    return _ORCH


def _bridge() -> AgenticRouterBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = AgenticRouterBridge(
            lower_threshold=settings.router_lower_threshold,
            higher_threshold=settings.router_higher_threshold,
            classifier_band=settings.router_classifier_band,
        )
    return _BRIDGE


# -- Tools --------------------------------------------------------------------
async def run_debate(
    message: Annotated[str, "The claim or debate topic to argue about."],
) -> str:
    """Run the real pro/cons debate orchestrator and return its event stream."""

    def _run() -> str:
        events = [e.to_dict() for e in _orchestrator().stream(message)]
        return json.dumps({"debate": events}, default=str)

    return await asyncio.to_thread(_run)


async def score_route(
    message: Annotated[str, "Message to score against the tiered model router."],
) -> str:
    """Score a message with the prototype's hybrid router (heuristic tier)."""

    def _run() -> str:
        b = _bridge()
        if b is None:
            return json.dumps(
                {"error": "router unavailable: agentic_router not vendored in this sandbox"},
            )
        score, signals = b.score(message)
        decision = b.decide(
            message,
            lower_model_name=settings.lower_model,
            higher_model_name=settings.higher_model,
            classifier_llm=None,  # heuristic-only in the sandbox (no vLLM)
        )
        return json.dumps(
            {"score": score, "signals": signals, "decision": decision.to_dict()},
            default=str,
        )

    return await asyncio.to_thread(_run)


# -- Graph --------------------------------------------------------------------
def _build_graph() -> Any:
    from langchain.agents import create_agent
    from langchain_core.tools import StructuredTool
    from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel

    chat_model = AzureAIOpenAIApiChatModel(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-5-mini"),
    )

    tools = [
        StructuredTool.from_function(coroutine=run_debate, name="run_debate"),
        StructuredTool.from_function(coroutine=score_route, name="score_route"),
    ]

    instructions = (
        "You are the front door of an agent-to-agent debate prototype. When the user states "
        "a claim or opinion, call run_debate with that claim and summarize the pro/cons "
        "arguments, the rebuttal exchange, and the final verdict concisely. When the user "
        "asks how a task would be routed between model tiers, call score_route and explain "
        "the decision. Be balanced and concise."
    )

    return create_agent(chat_model, tools=tools, system_prompt=instructions)


def main() -> None:
    graph = _build_graph()
    port = int(os.environ.get("PORT", "8088"))
    from langchain_azure_ai.agents.hosting import ResponsesHostServer

    ResponsesHostServer(graph).run(port=port)


if __name__ == "__main__":
    main()
