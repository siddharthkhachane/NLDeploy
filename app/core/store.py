from dataclasses import dataclass, field
from typing import Optional
import uuid
from datetime import datetime, timezone


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
activity_feed: list[dict] = []
MAX_ACTIVITY_ITEMS = 200


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


def add_activity(entry: dict) -> None:
    """Append a single activity item with UTC timestamp."""
    stamped = {"at": datetime.now(timezone.utc).isoformat(), **entry}
    activity_feed.append(stamped)
    if len(activity_feed) > MAX_ACTIVITY_ITEMS:
        del activity_feed[:-MAX_ACTIVITY_ITEMS]


def get_activity(limit: int = 50) -> list[dict]:
    """Return newest activity items first."""
    size = max(1, min(limit, MAX_ACTIVITY_ITEMS))
    return list(reversed(activity_feed[-size:]))
