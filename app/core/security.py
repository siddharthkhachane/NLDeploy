import subprocess
import re
import os


def runner_available() -> bool:
    """
    Check if deployment runner is available.
    
    Verifies:
    - ansible-playbook command exists
    - ansible/deploy.yml exists
    - ansible/inventory.ini exists
    - (optional) docker command exists
    
    Returns:
        True if runner is ready, False otherwise
    """
    checks = [
        ("ansible-playbook", _check_command_exists("ansible-playbook")),
        ("ansible/deploy.yml", os.path.exists("ansible/deploy.yml")),
        ("ansible/inventory.ini", os.path.exists("ansible/inventory.ini")),
    ]
    
    optional_checks = [
        ("docker", _check_command_exists("docker")),
    ]
    
    # All critical checks must pass
    for name, result in checks:
        if not result:
            return False
    
    return True


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
