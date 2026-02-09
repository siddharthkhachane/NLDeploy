import re
import os
import logging
from typing import Optional, Union
from app.core.models import DeploymentSpec, CommandSpec
from app.core.security import assess_command_risk

logger = logging.getLogger(__name__)


def parse_deploy_text(text: str) -> Union[DeploymentSpec, CommandSpec]:
    """
    Parse natural language deployment or command description.
    
    Detects if text is a command (stop, restart, scale) or deployment (version-based).
    Uses OpenAI ChatGPT API if OPENAI_API_KEY is set,
    otherwise falls back to regex parsing.
    
    Args:
        text: Natural language deployment/command description
        
    Returns:
        DeploymentSpec or CommandSpec with extracted fields
        
    Raises:
        ValueError: If parsing fails
    """
    if not text or not text.strip():
        raise ValueError("Deployment/command description cannot be empty")
    
    # Check if this is a command (stop, restart, scale) or deployment (version)
    command_type = detect_command_type(text)
    
    if command_type:
        # Parse as command
        logger.info(f"Detected command type: {command_type}")
        return parse_command_text(text, command_type)
    else:
        # Parse as deployment (version-based)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                spec = parse_with_chatgpt(text, api_key)
                logger.info(f"Parsed deployment with ChatGPT: {spec.target_version}")
                return spec
            except Exception as e:
                logger.warning(f"ChatGPT parsing failed: {str(e)}, falling back to regex")
        
        # Fallback to regex parsing
        return parse_with_regex(text)


def detect_command_type(text: str) -> Optional[str]:
    """
    Detect if text contains a command keyword (stop, restart, scale).
    
    Args:
        text: Text to analyze
        
    Returns:
        Command type string or None if no command detected
    """
    text_lower = text.lower()
    
    # Command keywords
    if re.search(r'\b(stop|shutdown|halt|terminate)\b', text_lower):
        return "stop"
    elif re.search(r'\b(restart|reboot|reload)\b', text_lower):
        return "restart"
    elif re.search(r'\b(scale|scale\s+up|scale\s+down)\b', text_lower):
        return "scale"
    
    return None


def extract_target_nodes(text: str) -> list[str]:
    """
    Extract target node names from text.
    
    Looks for node1, node2, node3 mentions.
    If no specific nodes mentioned, returns all nodes.
    
    Args:
        text: Text to search
        
    Returns:
        List of target node names
    """
    text_lower = text.lower()
    nodes = []
    
    if re.search(r'node\s*1|node1', text_lower):
        nodes.append("node1")
    if re.search(r'node\s*2|node2', text_lower):
        nodes.append("node2")
    if re.search(r'node\s*3|node3', text_lower):
        nodes.append("node3")
    
    # If no specific nodes, target all
    if not nodes:
        nodes = ["node1", "node2", "node3"]
    
    return nodes


def parse_command_text(text: str, command_type: str) -> CommandSpec:
    """
    Parse command specification from text.
    
    Args:
        text: Command description
        command_type: Type of command (stop, restart, scale)
        
    Returns:
        CommandSpec with command_type and target_nodes
        
    Raises:
        ValueError: If parsing fails
    """
    target_nodes = extract_target_nodes(text)
    
    if not target_nodes:
        target_nodes = ["node1", "node2", "node3"]
    
    scale_direction = "none"
    if command_type == "scale":
        text_lower = text.lower()
        if re.search(r"\bscale\s+down\b|\bdownscale\b", text_lower):
            scale_direction = "down"
        elif re.search(r"\bscale\s+up\b|\bupscale\b", text_lower):
            scale_direction = "up"

    spec = CommandSpec(
        command_type=command_type,
        target_nodes=target_nodes,
        scale_direction=scale_direction,
    )

    requires_confirmation, risk_reason = assess_command_risk(spec)
    spec.requires_confirmation = requires_confirmation
    spec.risk_reason = risk_reason

    return spec



def parse_with_chatgpt(text: str, api_key: str) -> DeploymentSpec:
    """
    Parse deployment description using OpenAI ChatGPT API.
    
    Sends text to GPT-4/GPT-3.5 to extract deployment spec fields.
    
    Args:
        text: Deployment description
        api_key: OpenAI API key
        
    Returns:
        DeploymentSpec with extracted fields
        
    Raises:
        Exception: If API call fails or parsing fails
    """
    import openai
    
    openai.api_key = api_key
    
    prompt = f"""Parse this deployment request and extract the spec fields in JSON format.
Return only valid JSON with these fields (string values):
- target_version: version to deploy (e.g., "v2", "v1.2.3") - REQUIRED
- strategy: deployment strategy, must be "rolling" - DEFAULT "rolling"
- batch_size: must be 1 - DEFAULT 1
- health_path: health check endpoint - DEFAULT "/health"
- retries: number of health check retries - DEFAULT 30
- delay_sec: delay between retries - DEFAULT 0.5

Request: "{text}"

Return ONLY valid JSON, no markdown, no explanation."""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a JSON parser for deployment specifications."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=200
    )
    
    response_text = response.choices[0].message.content.strip()
    
    import json
    spec_dict = json.loads(response_text)
    
    # Validate required field
    if "target_version" not in spec_dict or not spec_dict["target_version"]:
        raise ValueError("No target_version in ChatGPT response")
    
    return DeploymentSpec(**spec_dict)


def parse_with_regex(text: str) -> DeploymentSpec:
    """
    Parse deployment description using regex fallback.
    
    Extracts version token using pattern: v[0-9]+(\.[0-9]+)*
    
    Args:
        text: Deployment description
        
    Returns:
        DeploymentSpec with extracted target_version
        
    Raises:
        ValueError: If no version token found
    """
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
