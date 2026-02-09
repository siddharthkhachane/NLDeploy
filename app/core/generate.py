from app.core.models import DeploymentSpec


def generate_artifacts(spec: DeploymentSpec) -> dict:
    """
    Generate deployment artifacts from spec.
    
    Returns dict with:
    - spec: The deployment spec as dict
    - command: Ansible playbook command string
    - inventory_template: Example inventory.ini configuration
    - notes: Steps to run locally
    """
    command = (
        f"ansible-playbook -i ansible/inventory.ini ansible/deploy.yml "
        f"-e target_version={spec.target_version}"
    )
    if spec.failure_injection_node:
        command += f" -e force_fail_node={spec.failure_injection_node}"
    
    inventory_template = """[all]
node1 service_name=node1 host_port=18081
node2 service_name=node2 host_port=18082
node3 service_name=node3 host_port=18083"""
    
    notes = [
        "# Setup",
        "1. Ensure docker nodes are running: docker compose -f docker/docker-compose.yml up",
        "2. Install ansible: pip install ansible",
        "3. Verify ansible-playbook exists: which ansible-playbook",
        "",
        "# Deploy",
        f"4. Run deployment: {command}",
        "",
        "# Verify",
        "5. Check node versions: curl http://localhost:18081/version",
    ]

    risk_checks = [
        "Canary gate must pass before full rollout starts.",
        "Per-node health checks verify /health returns HTTP 200.",
        "Version checks verify /version includes target APP_VERSION.",
        "Auto-rollback executes if deployment exits non-zero."
    ]

    snippets = [
        "# Dry-run parse",
        f"POST /api/nlp/parse -> target_version={spec.target_version}",
        "",
        "# Planned deployment command",
        command,
        "",
        "# Verify canary manually",
        "curl http://localhost:18081/health",
        "curl http://localhost:18081/version",
    ]
    
    return {
        "spec": spec.model_dump(),
        "command": command,
        "inventory_template": inventory_template,
        "notes": notes,
        "snippets": snippets,
        "risk_checks": risk_checks,
        "impacted_nodes": ["node1", "node2", "node3"],
        "stages": ["parse", "plan", "canary", "rollout", "verify"]
    }
