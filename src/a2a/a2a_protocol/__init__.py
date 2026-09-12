"""A2A HTTP protocol: AgentCard discovery + JSON-RPC style /tasks endpoint.

This is a simplified, prototype-grade implementation of the Google A2A spec
(https://a2a-protocol.org). It exposes:
  * GET  /.well-known/agent.json  -> AgentCard
  * POST /tasks                   -> create a task, run synchronously, return result
  * GET  /tasks/{id}              -> fetch a stored task (best-effort, in-memory)
  * GET  /agents                  -> list peer agents this agent knows about

A client (``A2AClient``) lets agents invoke each other over HTTP, enabling true
agent-to-agent communication alongside the in-process LangGraph orchestration.
"""

from a2a.a2a_protocol.client import A2AClient
from a2a.a2a_protocol.schemas import A2AMessage, A2ATask, AgentCardModel
from a2a.a2a_protocol.server import build_app, serve_agent

__all__ = ["A2AMessage", "A2ATask", "AgentCardModel", "build_app", "serve_agent", "A2AClient"]