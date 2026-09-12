"""Command line interface for the a2a prototype."""

from __future__ import annotations

import argparse
import json
import sys

from a2a.agents import CoderAgent, ResearcherAgent, WriterAgent
from a2a.agents.llm import make_llm
from a2a.orchestration import SupervisorOrchestrator


def _build_agents(provider: str | None):
    llm = make_llm(provider)
    return [
        ResearcherAgent(llm=llm),
        WriterAgent(llm=llm),
        CoderAgent(llm=llm),
    ]


def cmd_run(args: argparse.Namespace) -> int:
    orchestrator = SupervisorOrchestrator(_build_agents(args.provider))
    result = orchestrator.run(args.prompt)
    print("\n=== Final answer ===")
    print(result.get("final", ""))
    print("\n=== Transcript ===")
    for m in result.get("messages", []):
        name = m.get("name", m["role"])
        print(f"[{name}] {m['content'][:300]}")
    return 0


def cmd_describe(_args: argparse.Namespace) -> int:
    orchestrator = SupervisorOrchestrator(_build_agents(None))
    print(json.dumps(orchestrator.describe(), indent=2))
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    from a2a.agents import ResearcherAgent
    from a2a.agents.llm import make_llm

    provider = args.provider if args.provider else "stub"
    agent = ResearcherAgent(llm=make_llm(provider))
    agent.run("Remember that the project deadline is Friday and uses Python 3.11.")
    agent.memory.learn_fact("project", "deadline", "Friday")
    agent.memory.learn_fact("project", "language", "Python 3.11")
    print("Short-term:", [r.content for r in agent.memory.short_term.all()])
    print("Facts:", agent.memory.semantic.all_facts())
    print("Episodes:", [e.summary() for e in agent.memory.episodic.all()])
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from a2a.a2a_protocol import serve_agent

    agents = {
        "researcher": ResearcherAgent,
        "writer": WriterAgent,
        "coder": CoderAgent,
    }
    if args.agent not in agents:
        print(f"Unknown agent: {args.agent}. Choose from {list(agents)}.")
        return 2
    agent = agents[args.agent](llm=make_llm(args.provider))
    serve_agent(agent, port=args.port)
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    from a2a.a2a_protocol import A2AClient

    client = A2AClient(args.url)
    if args.list_agents:
        print(json.dumps(client.list_agents(), indent=2))
        return 0
    if args.card:
        print(json.dumps(client.agent_card(), indent=2))
        return 0
    if not args.message:
        print("Provide --message, --card, or --list-agents.")
        return 2
    task = client.send_task(args.message, sender="cli")
    print(json.dumps(task.to_dict(), indent=2))
    return 0


def cmd_debate(args: argparse.Namespace) -> int:
    from a2a.debate import DebateOrchestrator, detect_debate_intent
    from a2a.router import make_routed_llm

    llm = make_routed_llm() if not args.provider else make_llm(args.provider)
    intent = detect_debate_intent(args.message, llm=llm)
    print(json.dumps(intent.to_dict(), indent=2))
    orch = DebateOrchestrator(llm=llm)
    result = orch.run(args.message)
    print("\n=== Events ===")
    for ev in result["events"]:
        label = ev.get("agent", ev["type"])
        if ev["type"] == "route":
            meta = ev.get("metadata", {})
            print(f"[route:{label}] tier={meta.get('tier')} model={meta.get('model')} "
                  f"method={meta.get('method')} score={meta.get('score')}")
        else:
            print(f"[{label}] {ev.get('content', '')[:240]}")
    print("\n=== Final ===")
    print(result["final"])
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from a2a.router import make_routed_llm
    from a2a.web import serve

    llm = make_routed_llm() if not args.provider else make_llm(args.provider)
    print(f"Starting chat UI at http://{args.host}:{args.port}")
    if hasattr(llm, "describe"):
        print("Router:", llm.describe())
    serve(host=args.host, port=args.port, llm=llm)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="a2a", description="A2A prototype CLI")
    p.add_argument("--provider", default=None, help="LLM provider (ollama|stub)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run a multi-agent workflow via LangGraph supervisor")
    r.add_argument("prompt", help="User prompt for the workflow")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("describe", help="Print agent cards")
    d.set_defaults(func=cmd_describe)

    m = sub.add_parser("memory", help="Demo the memory subsystems")
    m.set_defaults(func=cmd_memory)

    s = sub.add_parser("serve", help="Run an A2A HTTP server for an agent")
    s.add_argument("agent", help="Agent name: researcher|writer|coder")
    s.add_argument("--port", type=int, default=None)
    s.set_defaults(func=cmd_serve)

    c = sub.add_parser("call", help="Call an A2A HTTP server")
    c.add_argument("url", help="Base URL of the A2A server")
    c.add_argument("--message", help="Message to send as a task")
    c.add_argument("--card", action="store_true", help="Fetch agent card")
    c.add_argument("--list-agents", action="store_true", help="List known agents")
    c.set_defaults(func=cmd_call)

    dbt = sub.add_parser("debate", help="Run a pro/cons debate on the CLI")
    dbt.add_argument("message", help="Debate request, e.g. 'pros and cons of remote work'")
    dbt.add_argument(
        "--provider", default=None,
        help="Force a single LLM provider instead of the hybrid router",
    )
    dbt.set_defaults(func=cmd_debate)

    chat = sub.add_parser("chat", help="Launch the web chat UI (pro/cons debate)")
    chat.add_argument("--host", default="127.0.0.1")
    chat.add_argument("--port", type=int, default=8080)
    chat.add_argument(
        "--provider",
        default=None,
        help="Force a single LLM provider (e.g. stub) instead of the hybrid router",
    )
    chat.set_defaults(func=cmd_chat)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())