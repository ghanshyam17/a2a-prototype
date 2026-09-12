"""Deploy the a2a hosted agent to the Foundry ``agent-lab`` project.

Usage:
    python azure/deploy_hosted_agent.py            # create + route new version
    python azure/deploy_hosted_agent.py --wait     # also wait for active

Env:
    FOUNDRY_PROJECT_ENDPOINT (required)
    FOUNDRY_MODEL_NAME       (default gpt-5-mini)

This is the Python-SDK path from the Microsoft quickstart
(learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-hosted-agent),
kept in-repo so the project needs nothing outside itself.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointConfig,
    CodeConfiguration,
    CodeDependencyResolution,
    FixedRatioVersionSelectionRule,
    HostedAgentDefinition,
    ProtocolVersionRecord,
    VersionSelector,
)
from azure.identity import DefaultAzureCredential

HERE = Path(__file__).resolve().parent
SRC = (HERE / "hosted-agent" / "src").resolve()

EXCLUDED = {".git", ".venv", "__pycache__", ".env", "deploy_hosted_agent.py", ".pytest_cache"}


def create_code_zip(source_dir: Path) -> Path:
    zip_path = Path(tempfile.gettempdir()) / "a2a-hosted-agent.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED for part in path.parts):
                continue
            zf.write(path, path.relative_to(source_dir))
    return zip_path


def wait_for_active(client: AIProjectClient, agent_name: str, version: str) -> None:
    for attempt in range(60):
        time.sleep(10)
        details = client.agents.get_version(agent_name=agent_name, agent_version=version)
        status = details.get("status") if isinstance(details, dict) else getattr(details, "status", None)
        print(f"  provisioning: {status} ({attempt + 1}/60)")
        if status == "active":
            return
        if status == "failed":
            raise RuntimeError(f"provisioning failed: {details}")
    raise RuntimeError("timed out waiting for the hosted agent version")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()

    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    model = os.environ.get("FOUNDRY_MODEL_NAME", "gpt-5-mini")
    agent_name = os.environ.get("FOUNDRY_HOSTED_AGENT_NAME", "a2a-debate")

    zip_path = create_code_zip(SRC)
    print(f"code zip: {zip_path} ({zip_path.stat().st_size} bytes)")

    with zip_path.open("rb") as code_stream, DefaultAzureCredential() as cred, \
            AIProjectClient(endpoint=endpoint, credential=cred) as client:
        created = client.agents.create_version_from_code(
            agent_name=agent_name,
            description="a2a debate prototype: LangGraph pro/cons orchestration + tiered router",
            definition=HostedAgentDefinition(
                cpu="0.5",
                memory="1Gi",
                code_configuration=CodeConfiguration(
                    runtime="python_3_11",
                    entry_point=["python", "main.py"],
                    dependency_resolution=CodeDependencyResolution.REMOTE_BUILD,
                ),
                environment_variables={
                    "FOUNDRY_PROJECT_ENDPOINT": endpoint,
                    "AZURE_AI_MODEL_DEPLOYMENT_NAME": model,
                    "PYTHONPATH": ".",
                },
                protocol_versions=[ProtocolVersionRecord(protocol="responses", version="2.0.0")],
            ),
            code=code_stream,
        )
        print(f"created version {created.version}")

        if args.wait:
            wait_for_active(client, agent_name, created.version)

        client.agents.update_details(
            agent_name=agent_name,
            agent_endpoint=AgentEndpointConfig(
                version_selector=VersionSelector(
                    version_selection_rules=[
                        FixedRatioVersionSelectionRule(
                            agent_version=created.version, traffic_percentage=100
                        )
                    ]
                )
            ),
        )
        print("endpoint routed to", created.version)
        print(f"playground/endpoint: {endpoint}/agents/{agent_name}")


if __name__ == "__main__":
    main()
