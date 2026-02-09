from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class DeploymentStore:
    """In-memory state store for a deployment run"""
    running: bool = False
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    logs: list = field(default_factory=list)
    result: Optional[dict] = None
    rollback: Optional[dict] = None
    error: Optional[str] = None
    current_stage: str = "idle"
    timeline: list[dict] = field(default_factory=list)


# Global deployment state
current_deployment = DeploymentStore()


def reset_store():
    """Reset the deployment store"""
    global current_deployment
    current_deployment = DeploymentStore()


def get_store() -> DeploymentStore:
    """Get current deployment store"""
    global current_deployment
    return current_deployment


def set_store(store: DeploymentStore):
    """Set deployment store"""
    global current_deployment
    current_deployment = store
