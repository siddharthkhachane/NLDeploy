import subprocess
import re
import os
import logging

logger = logging.getLogger(__name__)


def get_ansible_command() -> str:
    """
    Get the ansible-playbook command that works on this system.
    
    Returns:
        "ansible-playbook" if available in PATH
        "wsl ansible-playbook" if only available in WSL
        None if not found
    """
    # Try Windows PATH first
    if _check_command_exists("ansible-playbook"):
        return "ansible-playbook"
    
    # Try WSL
    if _check_command_in_wsl("ansible-playbook"):
        return "wsl ansible-playbook"
    
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
