import re
from app.core.models import DeploymentSpec


def parse_deploy_text(text: str) -> DeploymentSpec:
    """
    Parse natural language deployment description and extract version token.
    
    Supports version formats like: v2, v10, v1.2.3, etc.
    
    Args:
        text: Natural language deployment description
        
    Returns:
        DeploymentSpec with extracted target_version
        
    Raises:
        ValueError: If no version token found in text
    """
    if not text or not text.strip():
        raise ValueError("Deployment description cannot be empty")
    
    # Regex pattern to match version tokens: v2, v10, v1.2.3, etc.
    version_pattern = r'v(\d+(?:\.\d+)*)'
    
    matches = re.findall(version_pattern, text, re.IGNORECASE)
    
    if not matches:
        raise ValueError(
            f"No version token found in text. "
            f"Expected format like 'v2', 'v10', or 'v1.2.3'. "
            f"Got: '{text}'"
        )
    
    # Use the first version token found
    version_token = f"v{matches[0]}"
    
    return DeploymentSpec(target_version=version_token)
