# a2a — Agent-to-Agent Communication & Memory Prototype

A prototype of **agent-to-agent (A2A) communication** and a **full per-agent
memory architecture** with **multi-agent orchestration via LangGraph**.

## Features

- **Hybrid communication**: in-process LangGraph orchestration **+** an A2A
  HTTP protocol (AgentCard discovery + JSON-RPC-style `/tasks`) on FastAPI so
  external agents can join.
- **Full memory per agent**:
  - `ShortTermMemory` — rolling conversation buffer
  - `LongTermMemory` — vector store with cosine similarity retrieval
  - `EpisodicMemory` — time-stamped episodes for reflection/replay
  - `SemanticMemory` — durable facts / knowledge
  - `SharedScratchpad` — singleton coordination space (notes, tasks, kv)
  - `AgentMemory` — facade that bundles them all
- **LangGraph supervisor orchestration**: an LLM routes each step to one of
  the registered agents or to `FINISH`.
- **Chat web UI**: a FastAPI + HTML/JS chat interface with a live
  **agent-to-agent communication panel**. Intent detection on your chat
  message decides whether to run a pro/cons debate and which side(s) to invoke.
- **Pro/Cons debate**: a `ProAgent` (skills: pros) and a `ConsAgent` (skills:
  cons) debate a topic you provide. The agents exchange rebuttals directly
  (visible in the side panel) and post notes to the shared scratchpad.
- **LLM**: Ollama by default (`langchain-ollama`); a `StubLLM` fallback keeps
  the demo runnable offline.
- **Sample agents**: `ResearcherAgent`, `WriterAgent`, `CoderAgent`,
  `ProAgent`, `ConsAgent`.

## Layout

```
src/a2a/
  config.py              # env-driven settings
  cli.py                 # `a2a` command
  memory/
    base.py              # MemoryRecord
    embeddings.py        # Ollama + hashing fallback embedders
    short_term.py
    long_term.py
    episodic.py
    semantic.py
    shared.py            # SharedScratchpad singleton
    agent_memory.py      # AgentMemory facade
  agents/
    base.py              # BaseAgent, AgentCard, LLMClient protocol
    llm.py               # OllamaLLM, StubLLM, make_llm
    researcher.py
    writer.py
    coder.py
    pro.py               # ProAgent (skills: pros)
    cons.py              # ConsAgent (skills: cons)
  orchestration/
    supervisor.py        # LangGraph SupervisorOrchestrator
  debate/
    intent.py            # detect_debate_intent (chat-as-interface intent detection)
    orchestrator.py      # DebateOrchestrator + DebateEvent streaming
  a2a_protocol/
    schemas.py           # AgentCardModel, A2AMessage, A2ATask
    server.py            # FastAPI build_app + serve_agent
    client.py            # A2AClient (httpx)
  web/
    app.py               # chat UI FastAPI app + SSE /api/chat
    static/index.html    # chat panel + agent-to-agent panel (HTML/JS)
tests/
  test_smoke.py
  test_debate.py
```

## Quick start

```bash
# 1. Install (uv recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env            # tweak models / ports if needed

# 2. Make sure Ollama is running locally
ollama serve &
ollama pull llama3.1
ollama pull nomic-embed-text

# 3. Run the smoke tests (works without Ollama via StubLLM)
pytest -q

# 4. Run a multi-agent workflow through the LangGraph supervisor
a2a run "Write a short blog intro about retrieval-augmented generation."

# 5. Launch the chat web UI (pro/cons debate with live agent-to-agent panel)
a2a chat --port 8080
#   then open http://127.0.0.1:8080 and type e.g.
#   "Give me pros and cons of remote work"

# 6. Run a debate on the CLI directly
a2a debate "pros and cons of remote work"

# 7. Inspect memory subsystems
a2a memory

# 8. Serve an agent over the A2A HTTP protocol
a2a serve researcher --port 8001 &

# 9. Call it from another process / agent
a2a call http://localhost:8001 --card
a2a call http://localhost:8001 --message "Summarize RAG in 2 sentences."
```

## How A2A communication works

Two complementary paths:

1. **In-process (LangGraph)** — `SupervisorOrchestrator` builds a
   `StateGraph` whose `supervisor` node uses an LLM to pick the next agent
   node. Agents share a `SharedScratchpad` and each keeps its own
   `AgentMemory` across the run. See `orchestration/supervisor.py`.

2. **Over HTTP (A2A protocol)** — each agent can be served via FastAPI
   (`a2a_protocol/server.py`) exposing `/.well-known/agent.json`,
   `POST /tasks`, `GET /tasks/{id}` and `GET /agents`. Other agents or
   clients use `A2AClient` (`a2a_protocol/client.py`) to invoke peers.

An agent in one process can therefore collaborate with an agent in another
process by POSTing a task, while memory stays local to each.

## Chat UI & pro/cons debate

`a2a chat` launches a web UI (`web/app.py` + `web/static/index.html`) with two
panes:

- **Left — Chat**: your interface to the agents. Type a request like
  *"Give me pros and cons of remote work"*.
- **Right — Agent-to-Agent**: a live panel showing direct agent-to-agent
  messages (rebuttals, shared-board notes) as they happen.

### Flow

1. **Intent detection** (`debate/intent.py`): your chat message is parsed by
   `detect_debate_intent` (LLM when available, heuristic fallback) to decide:
   - `is_debate` — is this a pros/cons request?
   - `topic` — the subject to debate
   - `side` — `"pro"`, `"cons"`, or `"both"`
   The detected intent is shown in the chat as an `intent` event.
2. **Agent 1 — Pro** (`agents/pro.py`, skills: `pros`): if `side` includes
   `pro`, the Pro agent produces 3-5 arguments in favour of `topic`. Shown as
   a green chat message.
3. **Agent 2 — Cons** (`agents/cons.py`, skills: `cons`): if `side` includes
   `cons`, the Cons agent produces 3-5 arguments against `topic`. Shown as a
   red chat message.
4. **Agent-to-agent rebuttals**: when `side == "both"`, each agent sees the
   other's arguments (posted on the shared scratchpad) and writes a focused
   rebuttal. These `agent_comm` events (pro → cons, then cons → pro) are
   rendered live in the right-hand panel with `sender → receiver` arrows.
5. **Final summary**: a `final` event aggregates both sides.

All events are streamed from `POST /api/chat` as Server-Sent Events; the
browser renders them as they arrive. Try the example chips under the input bar.

The same flow is available on the CLI via `a2a debate "<message>"`.

## Memory architecture

Each `BaseAgent` owns an `AgentMemory` instance aggregating:

| Store         | Purpose                              | Backed by (prototype)       |
|---------------|--------------------------------------|-----------------------------|
| Short-term    | Current conversation window          | `deque` (bounded)           |
| Long-term     | Retrieval over past interactions     | in-process vector + cosine  |
| Episodic      | Sequences of events / task replays   | `Episode` list              |
| Semantic      | Durable facts                        | nested dict                 |
| Shared        | Cross-agent coordination             | thread-safe singleton       |

The vector store and semantic store are intentionally simple so they can be
swapped for Chroma/pgvector/Neo4j without touching agent code.

## Configuration

Environment variables (see `.env.example`):

```
MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
A2A_HOST=127.0.0.1
A2A_PORT_BASE=8000
```

## Lint / typecheck

```bash
ruff check .
mypy src/a2a
```

## Status

Prototype-grade. Not production hardened. The A2A HTTP subset is simplified
from the Google A2A spec for demonstration purposes.