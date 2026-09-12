"""Smoke-test the deployed hosted agent (Responses protocol, Entra auth).

Usage:
    python azure/scripts/smoke.py --message "Debate: tabs beat spaces"
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

from azure.identity import DefaultAzureCredential


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", required=True)
    ap.add_argument("--endpoint")
    args = ap.parse_args()

    project = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    agent = os.environ.get("FOUNDRY_HOSTED_AGENT_NAME", "a2a-debate")
    url = f"{project}/agents/{agent}/endpoint/protocols/openai/responses?api-version=v1"

    cred = DefaultAzureCredential()
    token = cred.get_token("https://cognitiveservices.azure.com/.default").token

    payload = json.dumps(
        {
            "model": os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-5-mini"),
            "input": args.message,
            "stream": False,
        }
    ).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode())

    # Responses API: answer text lives in output[] items of type "message".
    texts = []
    for item in body.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") in ("output_text", "text"):
                    texts.append(part.get("text", ""))
    print(json.dumps({"status": "ok", "reply": "\n".join(texts) or body}, indent=2)[:2000])


if __name__ == "__main__":
    main()
