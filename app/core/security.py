import subprocess
import re
import os
import logging

logger = logging.getLogger(__name__)


def runner_available() -> bool:
    """
    Check if deployment runner is available.
    
    Verifies:
    - ansible-playbook command exists
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
    has_ansible = _check_command_exists("ansible-playbook")
    
    if not has_ansible:
        logger.warning("ansible-playbook not found in PATH")
        # On Windows, Ansible might be in WSL or requires special setup
        # Log a helpful message but still return False
        logger.info("Windows detected - Ansible may need WSL setup. See README for setup instructions.")
    
    return has_ansible


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
