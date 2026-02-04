import pytest
from app.core.nlp import parse_deploy_text
from app.core.models import DeploymentSpec


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
