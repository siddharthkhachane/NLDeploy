import pytest
from pydantic import ValidationError
from app.core.models import DeploymentSpec


def test_spec_basic():
    """Test basic spec creation with required field"""
    spec = DeploymentSpec(target_version="v2")
    assert spec.target_version == "v2"
    assert spec.strategy == "rolling"
    assert spec.batch_size == 1


def test_spec_with_all_fields():
    """Test spec with all custom fields"""
    spec = DeploymentSpec(
        target_version="v1.2.3",
        strategy="rolling",
        batch_size=1,
        health_path="/status",
        retries=50,
        delay_sec=1.0
    )
    assert spec.target_version == "v1.2.3"
    assert spec.health_path == "/status"
    assert spec.retries == 50
    assert spec.delay_sec == 1.0


def test_spec_batch_size_validation():
    """Test batch_size must be 1"""
    with pytest.raises(ValidationError) as exc_info:
        DeploymentSpec(target_version="v2", batch_size=2)
    
    assert "batch_size must equal 1" in str(exc_info.value)


def test_spec_target_version_required():
    """Test target_version is required"""
    with pytest.raises(ValidationError):
        DeploymentSpec()


def test_spec_target_version_empty():
    """Test empty target_version is invalid"""
    with pytest.raises(ValidationError) as exc_info:
        DeploymentSpec(target_version="")
    
    assert "target_version is required" in str(exc_info.value)


def test_spec_defaults():
    """Test default values"""
    spec = DeploymentSpec(target_version="v2")
    assert spec.strategy == "rolling"
    assert spec.batch_size == 1
    assert spec.health_path == "/health"
    assert spec.retries == 30
    assert spec.delay_sec == 0.5
