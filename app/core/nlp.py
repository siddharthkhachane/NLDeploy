import re
import os
import logging
from typing import Optional
from app.core.models import DeploymentSpec

logger = logging.getLogger(__name__)


def parse_deploy_text(text: str) -> DeploymentSpec:
    """
    Parse natural language deployment description.
    
    Uses OpenAI ChatGPT API if OPENAI_API_KEY is set,
    otherwise falls back to regex parsing.
    
    Args:
        text: Natural language deployment description
        
    Returns:
        DeploymentSpec with extracted fields
        
    Raises:
        ValueError: If parsing fails or no version found
    """
    if not text or not text.strip():
        raise ValueError("Deployment description cannot be empty")
    
    # Try ChatGPT first if API key available
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            spec = parse_with_chatgpt(text, api_key)
            logger.info(f"Parsed with ChatGPT: {spec.target_version}")
            return spec
        except Exception as e:
            logger.warning(f"ChatGPT parsing failed: {str(e)}, falling back to regex")
    
    # Fallback to regex parsing
    return parse_with_regex(text)


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
