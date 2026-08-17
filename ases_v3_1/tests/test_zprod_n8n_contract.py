import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

import pytest

N8N_PATH = Path(__file__).resolve().parents[1] / "n8n_orchestrator.json"
DATA = json.loads(N8N_PATH.read_text(encoding="utf-8"))
NODES = DATA["nodes"]
NODE_NAMES = {node["name"] for node in NODES}


@pytest.mark.parametrize("node", NODES, ids=[node["id"] for node in NODES])
def test_node_has_required_fields(node):
    assert node.get("id")
    assert node.get("name")
    assert node.get("type")
    assert isinstance(node.get("position"), list)
    assert len(node["position"]) == 2


CONNECTION_CASES = [
    (source, target["node"])
    for source, connections in DATA["connections"].items()
    for branch in connections.get("main", [])
    for target in branch
]


@pytest.mark.parametrize(
    "source,target",
    CONNECTION_CASES,
    ids=[f"{source}->{target}" for source, target in CONNECTION_CASES],
)
def test_connections_reference_existing_nodes(source, target):
    assert source in NODE_NAMES
    assert target in NODE_NAMES


REQUIRED_ENVS = [
    "AGENT_SERVICE_URL",
    "TENANT_ID",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_BOT_TOKEN",
    "OUTREACH_FROM_EMAIL",
]


@pytest.mark.parametrize("env_var", REQUIRED_ENVS, ids=REQUIRED_ENVS)
def test_required_env_vars_are_referenced(env_var):
    raw = N8N_PATH.read_text(encoding="utf-8")
    assert env_var in raw


@pytest.mark.parametrize("secret_prefix", ["sk-ghp_", "ghp_ywMF", "BEGIN PRIVATE KEY"], ids=["openai", "github", "private-key"])
def test_no_hardcoded_secrets(secret_prefix):
    raw = N8N_PATH.read_text(encoding="utf-8")
    assert secret_prefix not in raw
