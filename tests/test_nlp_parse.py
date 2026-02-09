import pytest
from app.core.nlp import parse_deploy_text, detect_command_type, extract_target_nodes
from app.core.models import DeploymentSpec, CommandSpec


def test_parse_simple_version():
    """Test parsing simple version format v2"""
    spec = parse_deploy_text("Deploy version v2 to all nodes")
    assert isinstance(spec, DeploymentSpec)
    assert spec.target_version == "v2"


def test_parse_version_v10():
    """Test parsing two-digit version v10"""
    spec = parse_deploy_text("Deploy v10 to production")
    assert spec.target_version == "v10"


def test_parse_semver():
    """Test parsing semantic version v1.2.3"""
    spec = parse_deploy_text("Update to v1.2.3")
    assert spec.target_version == "v1.2.3"


def test_parse_version_with_more_parts():
    """Test parsing version with many parts"""
    spec = parse_deploy_text("Release v2.1.4.5 now")
    assert spec.target_version == "v2.1.4.5"


def test_parse_first_version():
    """Test that first version token is used"""
    spec = parse_deploy_text("Deploy v2 then rollback to v1")
    assert spec.target_version == "v2"


def test_parse_case_insensitive():
    """Test version parsing is case insensitive"""
    spec = parse_deploy_text("Deploy V2 to all nodes")
    assert spec.target_version == "v2"


def test_parse_no_version():
    """Test error when no version found"""
    with pytest.raises(ValueError) as exc_info:
        parse_deploy_text("Deploy to all nodes")
    
    assert "No version token found" in str(exc_info.value)
    assert "v2" in str(exc_info.value)  # Shows example format


def test_parse_empty_text():
    """Test error on empty text"""
    with pytest.raises(ValueError) as exc_info:
        parse_deploy_text("")
    
    assert "cannot be empty" in str(exc_info.value)


def test_parse_whitespace_only():
    """Test error on whitespace only"""
    with pytest.raises(ValueError):
        parse_deploy_text("   ")


# Command Parsing Tests

def test_detect_command_stop():
    """Test detecting stop command"""
    cmd_type = detect_command_type("Stop node1")
    assert cmd_type == "stop"


def test_detect_command_restart():
    """Test detecting restart command"""
    cmd_type = detect_command_type("Restart all nodes")
    assert cmd_type == "restart"


def test_detect_command_scale():
    """Test detecting scale command"""
    cmd_type = detect_command_type("Scale up the services")
    assert cmd_type == "scale"


def test_detect_command_case_insensitive():
    """Test command detection is case insensitive"""
    assert detect_command_type("STOP node1") == "stop"
    assert detect_command_type("ReStArT node2") == "restart"


def test_detect_no_command():
    """Test no command detected for version"""
    cmd_type = detect_command_type("Deploy v2")
    assert cmd_type is None


def test_extract_single_node():
    """Test extracting single node"""
    nodes = extract_target_nodes("Stop node1")
    assert "node1" in nodes


def test_extract_multiple_nodes():
    """Test extracting multiple nodes"""
    nodes = extract_target_nodes("Stop node1 and node2")
    assert "node1" in nodes
    assert "node2" in nodes


def test_extract_all_nodes_default():
    """Test all nodes returned when none specified"""
    nodes = extract_target_nodes("Stop all nodes")
    assert set(nodes) == {"node1", "node2", "node3"}


def test_parse_stop_command():
    """Test parsing stop command"""
    spec = parse_deploy_text("Stop node2")
    assert isinstance(spec, CommandSpec)
    assert spec.command_type == "stop"
    assert "node2" in spec.target_nodes


def test_parse_restart_command():
    """Test parsing restart command"""
    spec = parse_deploy_text("Restart all services")
    assert isinstance(spec, CommandSpec)
    assert spec.command_type == "restart"
    assert set(spec.target_nodes) == {"node1", "node2", "node3"}


def test_parse_command_with_node_filter():
    """Test parsing command with specific node"""
    spec = parse_deploy_text("Restart node1 and node3")
    assert isinstance(spec, CommandSpec)
    assert spec.command_type == "restart"
    assert "node1" in spec.target_nodes
    assert "node3" in spec.target_nodes


def test_parse_stop_all_requires_confirmation():
    spec = parse_deploy_text("Stop all nodes")
    assert isinstance(spec, CommandSpec)
    assert spec.requires_confirmation is True
    assert spec.risk_reason is not None


def test_parse_scale_down_requires_confirmation():
    spec = parse_deploy_text("Scale down node1")
    assert isinstance(spec, CommandSpec)
    assert spec.command_type == "scale"
    assert spec.scale_direction == "down"
    assert spec.requires_confirmation is True

