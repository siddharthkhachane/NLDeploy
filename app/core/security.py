import subprocess
import re
import os
import logging
from typing import Optional

from app.core.models import CommandSpec

logger = logging.getLogger(__name__)

ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"

ALLOWED_ROLES = {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN}


def get_ansible_command() -> Optional[list[str]]:
    """
    Get the ansible-playbook command that works on this system.
    
    Returns:
        ["ansible-playbook"] if available in PATH
        ["wsl", "ansible-playbook"] if only available in WSL
        None if not found
    """
    # Try Windows PATH first
    if _check_command_exists("ansible-playbook"):
        return ["ansible-playbook"]
    
    # Try WSL default distro first
    if _check_command_in_wsl("ansible-playbook"):
        return ["wsl", "ansible-playbook"]

    # Try explicit non-Docker WSL distros (e.g., Ubuntu)
    distro = _find_wsl_distro_with_command("ansible-playbook")
    if distro:
        return ["wsl", "-d", distro, "ansible-playbook"]
    
    return None


def _check_command_in_wsl(cmd: str) -> bool:
    """Check if command exists in WSL"""
    try:
        result = subprocess.run(
            ["wsl", "which", cmd],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def _list_wsl_distros() -> list[str]:
    """List available WSL distros (excluding empty lines)."""
    try:
        result = subprocess.run(
            ["wsl", "-l", "-q"],
            capture_output=True,
            timeout=3
        )
        if result.returncode != 0:
            return []

        # `wsl -l -q` commonly emits UTF-16LE bytes on Windows.
        raw = result.stdout or b""
        try:
            text = raw.decode("utf-16le")
        except UnicodeDecodeError:
            text = raw.decode(errors="ignore")

        return [line.strip().replace("\x00", "") for line in text.splitlines() if line.strip()]
    except Exception:
        return []


def _find_wsl_distro_with_command(cmd: str) -> Optional[str]:
    """
    Find a WSL distro that has the requested command.

    Docker Desktop distros are skipped because they usually do not have apt/ansible.
    """
    distros = _list_wsl_distros()
    for distro in distros:
        lower = distro.lower()
        if "docker-desktop" in lower:
            continue
        try:
            result = subprocess.run(
                ["wsl", "-d", distro, "which", cmd],
                capture_output=True,
                timeout=4
            )
            if result.returncode == 0:
                return distro
        except Exception:
            continue
    return None


def runner_available() -> bool:
    """
    Check if deployment runner is available.
    
    Verifies:
    - ansible-playbook command exists (Windows or WSL)
    - ansible/deploy.yml exists
    - ansible/inventory.ini exists
    
    Returns:
        True if runner is ready, False otherwise
    """
    # Check critical files first
    has_deploy_yml = os.path.exists("ansible/deploy.yml")
    has_inventory = os.path.exists("ansible/inventory.ini")
    
    if not (has_deploy_yml and has_inventory):
        logger.warning(f"Missing Ansible files: deploy.yml={has_deploy_yml}, inventory.ini={has_inventory}")
        return False
    
    # Check for ansible-playbook command
    ansible_cmd = get_ansible_command()
    
    if not ansible_cmd:
        logger.warning("ansible-playbook not found in PATH or WSL")
        logger.info("Install Ansible: pip install ansible (Windows) or wsl pip install ansible")
    
    return ansible_cmd is not None


def _check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH"""
    try:
        result = subprocess.run(
            ["which", cmd] if os.name != "nt" else ["where", cmd],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def validate_version_string(version: str) -> bool:
    """
    Validate version string format.
    
    Enforces pattern: v[0-9]+(\.[0-9]+)*
    Examples: v1, v2, v10, v1.2, v1.2.3
    
    Args:
        version: Version string to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r"^v[0-9]+(\.[0-9]+)*$"
    return bool(re.match(pattern, version))


def assess_command_risk(spec: CommandSpec) -> tuple[bool, Optional[str]]:
    """
    Assess whether a command should require explicit confirmation.
    """
    targets_all_nodes = set(spec.target_nodes) == {"node1", "node2", "node3"}

    if spec.command_type == "stop" and targets_all_nodes:
        return True, "Stopping all nodes can cause full service downtime."

    if spec.command_type == "scale" and spec.scale_direction == "down":
        return True, "Scale down can reduce capacity and availability."

    return False, None


def validate_command_execution(spec: CommandSpec) -> None:
    """
    Enforce confirmation for risky commands before execution.
    """
    requires_confirmation, risk_reason = assess_command_risk(spec)
    if requires_confirmation and not spec.confirmed:
        raise ValueError(
            risk_reason or "Risky command requires explicit confirmation."
        )

    if spec.command_type == "stop":
        expected = f"STOP {spec.environment}"
        provided = (spec.stop_guard_token or "").strip()
        if provided != expected:
            raise ValueError(f"Stop safeguard failed. Type exactly '{expected}' to continue.")


def normalize_role(role: Optional[str]) -> str:
    """
    Normalize role input to a safe role value.
    Defaults to admin to preserve existing behavior for old clients.
    """
    if not role:
        return ROLE_ADMIN
    normalized = role.strip().lower()
    if normalized in ALLOWED_ROLES:
        return normalized
    return ROLE_VIEWER


def authorize_action(role: str, action: str) -> bool:
    """
    Basic RBAC matrix:
    - viewer: read-only
    - operator: deploy + rollback
    - admin: deploy + rollback + stop/restart/scale commands
    """
    matrix = {
        ROLE_VIEWER: set(),
        ROLE_OPERATOR: {"deploy", "rollback"},
        ROLE_ADMIN: {"deploy", "rollback", "stop", "restart", "scale"},
    }
    return action in matrix.get(role, set())
