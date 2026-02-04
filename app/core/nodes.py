import httpx
from typing import Dict


# Node configuration
NODES = {
    "node1": {"port": 18081, "service_name": "node1"},
    "node2": {"port": 18082, "service_name": "node2"},
    "node3": {"port": 18083, "service_name": "node3"},
}


async def fetch_versions() -> Dict[str, str]:
    """
    Fetch current versions from all nodes.
    
    Returns:
        Dict mapping node name to version string
    """
    versions = {}
    
    async with httpx.AsyncClient() as client:
        for name, config in NODES.items():
            base_url = f"http://localhost:{config['port']}"
            try:
                resp = await client.get(f"{base_url}/version", timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    versions[name] = data.get("version", "unknown")
                else:
                    versions[name] = "unknown"
            except Exception:
                versions[name] = "unknown"
    
    return versions
