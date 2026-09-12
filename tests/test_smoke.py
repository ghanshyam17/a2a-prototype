"""Smoke tests that do not require an LLM server."""

from __future__ import annotations

from a2a.agents import ResearcherAgent, WriterAgent
from a2a.agents.llm import StubLLM
from a2a.memory import AgentMemory, SharedScratchpad
from a2a.orchestration import SupervisorOrchestrator


def test_memory_subsystems_store_and_retrieve():
    mem = AgentMemory("tester")
    mem.remember("user", "Please use Python 3.11 for the project.")
    mem.learn_fact("project", "language", "Python 3.11")
    mem.learn_fact("project", "deadline", "Friday")
    assert mem.semantic.get("project", "language") == "Python 3.11"
    assert len(mem.short_term.all()) == 1
    assert len(mem.episodic.all()) >= 1
    hits = mem.recall("Python project")
    assert any("Python 3.11" in h.content for h in hits)


def test_shared_scratchpad_is_singleton_and_threadsafe():
    a = SharedScratchpad()
    b = SharedScratchpad()
    assert a is b
    a.post_note("tester", "hello")
    notes = a.recent_notes()
    assert any("hello" in n.content for n in notes)


def test_agent_run_records_memory():
    llm = StubLLM()
    agent = ResearcherAgent(llm=llm)
    out = agent.run("Tell me about RAG architectures.")
    assert out.startswith("[stub]")
    assert len(agent.memory.short_term.all()) == 2
    assert agent.memory.episodic.latest() is not None


def test_supervisor_orchestrator_routes_and_finishes():
    llm = StubLLM()
    agents = [ResearcherAgent(llm=llm), WriterAgent(llm=llm)]
    orch = SupervisorOrchestrator(agents, llm=llm)
    result = orch.run("Write a one-paragraph summary of RAG.")
    assert result["final"]
    assert result["iterations"] >= 1


def test_agent_to_agent_direct_message():
    llm = StubLLM()
    researcher = ResearcherAgent(llm=llm)
    writer = WriterAgent(llm=llm)
    reply = researcher.send_to(writer, "Please draft an intro.")
    assert reply.startswith("[stub]")
    notes = researcher.memory.shared.recent_notes()
    assert any("-> writer" in n.content for n in notes)