import pytest
from app.core.generate import generate_artifacts
from app.core.models import DeploymentSpec


def test_generate_basic():
    """Test basic artifact generation"""
    spec = DeploymentSpec(target_version="v2")
    artifacts = generate_artifacts(spec)
    
    assert "spec" in artifacts
    assert "command" in artifacts
    assert "inventory_template" in artifacts
    assert "notes" in artifacts
    assert "risk_checks" in artifacts
    assert "snippets" in artifacts


def test_generate_spec_in_output():
    """Test spec is included in output"""
    spec = DeploymentSpec(target_version="v1.2.3", retries=50)
    artifacts = generate_artifacts(spec)
    
    output_spec = artifacts["spec"]
    assert output_spec["target_version"] == "v1.2.3"
    assert output_spec["retries"] == 50


def test_generate_command():
    """Test ansible command is generated correctly"""
    spec = DeploymentSpec(target_version="v2")
    artifacts = generate_artifacts(spec)
    
    command = artifacts["command"]
    assert "ansible-playbook" in command
    assert "-i ansible/inventory.ini" in command
    assert "ansible/deploy.yml" in command
    assert "-e target_version=v2" in command


def test_generate_command_with_custom_version():
    """Test command uses custom version"""
    spec = DeploymentSpec(target_version="v3.1.0")
    artifacts = generate_artifacts(spec)
    
    assert "-e target_version=v3.1.0" in artifacts["command"]


def test_generate_inventory_template():
    """Test inventory template is included"""
    spec = DeploymentSpec(target_version="v2")
    artifacts = generate_artifacts(spec)
    
    inventory = artifacts["inventory_template"]
    assert "node1" in inventory
    assert "node2" in inventory
    assert "node3" in inventory
    assert "18081" in inventory
    assert "18082" in inventory
    assert "18083" in inventory


def test_generate_notes():
    """Test setup notes are included"""
    spec = DeploymentSpec(target_version="v2")
    artifacts = generate_artifacts(spec)
    
    notes = artifacts["notes"]
    assert isinstance(notes, list)
    assert len(notes) > 0
    
    # Check for key steps
    notes_text = "\n".join(notes)
    assert "docker compose" in notes_text
    assert "ansible" in notes_text
    assert "curl" in notes_text


def test_generate_failure_injection_command():
    spec = DeploymentSpec(target_version="v2", failure_injection_node="node2")
    artifacts = generate_artifacts(spec)
    assert "force_fail_node=node2" in artifacts["command"]
