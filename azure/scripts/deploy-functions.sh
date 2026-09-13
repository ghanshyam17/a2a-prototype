#!/usr/bin/env bash
# Assemble + deploy the a2a-debate Function app via `func publish` (remote build).
# Python v2 model: function_app.py sits at the app ROOT.
set -euo pipefail
RG="${RG:-my-foundry-rg}"
APP="${APP:-a2a-agent-api}"
FUNC_BIN="${FUNC_BIN:-$HOME/bin/func-cli/func}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp "$ROOT/azure/functions/host.json" "$STAGE/"
cp "$ROOT/azure/functions/requirements.txt" "$STAGE/"
cp "$ROOT/azure/functions/agent-api/function_app.py" "$STAGE/"
mkdir -p "$STAGE/_vendor"
cp -R "$ROOT/src/a2a" "$STAGE/_vendor/a2a"

# a2a's router bridge imports agentic_router (+ components_core) from the
# sibling monorepo checkout; vendor it when present (heuristic path only).
SIBLING="$ROOT/../agent-components"
[ -d "$SIBLING/components/agentic-router/agentic_router" ] && \
  cp -R "$SIBLING/components/agentic-router/agentic_router" "$STAGE/_vendor/agentic_router"
[ -d "$SIBLING/core/src/components_core" ] && \
  cp -R "$SIBLING/core/src/components_core" "$STAGE/_vendor/components_core"

find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "deploying $APP from $STAGE"
(cd "$STAGE" && "$FUNC_BIN" azure functionapp publish "$APP" --python) | tail -8
