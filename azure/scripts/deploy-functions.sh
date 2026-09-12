#!/usr/bin/env bash
# Assemble + deploy the Function app (Consumption plan -> $0 when idle).
# Prereqs: az login; func CLI (npm i -g azure-functions-core-tools@4 --unsafe-perm true)
set -euo pipefail

RG="${RG:-my-foundry-rg}"
LOC="${LOC:-eastus}"
PREFIX="${PREFIX:-a2a}"
APP="${APP:-${PREFIX}-agent-api}"

ST=$(az storage account list -g "$RG" --query "[?starts_with(name,'${PREFIX}')].name" -o tsv | head -1)
if [ -z "$ST" ]; then
  ST="${PREFIX}$(head -c6 /dev/urandom | base64 | tr -dc a-z0-9 | head -c 6)st"
  az storage account create -g "$RG" -n "$ST" -l "$LOC" --sku Standard_LRS >/dev/null
fi

if ! az functionapp show -g "$RG" -n "$APP" >/dev/null 2>&1; then
  az functionapp create -g "$RG" -n "$APP" --storage-account "$ST" \
    --consumption-plan-location "$LOC" --runtime python --runtime-version 3.11 \
    --functions-version 4 --os-type Linux >/dev/null
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$ROOT/azure/functions/"* "$STAGE/"
mkdir -p "$STAGE/_vendor"
cp -R "$ROOT/src/a2a" "$STAGE/_vendor/a2a"

echo "deploying $APP from $STAGE"
(cd "$STAGE" && func azure functionapp publish "$APP" --python)
