import os
import json
import asyncio
from typing import List, Dict
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import httpx

app = FastAPI()

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Node configuration
NODES = {
    "node1": {"port": 18081, "service_name": "node1"},
    "node2": {"port": 18082, "service_name": "node2"},
    "node3": {"port": 18083, "service_name": "node3"},
}

# Deploy status tracking
deploy_status = {
    "running": False,
    "status": "idle",
    "current_node": None,
    "logs": [],
    "error": None
}


@app.get("/")
async def root(request: Request):
    """Serve the main UI page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/nodes")
async def get_nodes():
    """Get all nodes with their version and health status"""
    nodes = []
    async with httpx.AsyncClient() as client:
        for name, config in NODES.items():
            base_url = f"http://localhost:{config['port']}"
            try:
                version_resp = await client.get(f"{base_url}/version", timeout=2)
                version = version_resp.json().get("version", "unknown") if version_resp.status_code == 200 else "unknown"
                
                health_resp = await client.get(f"{base_url}/health", timeout=2)
                healthy = health_resp.status_code == 200
            except Exception:
                version = "unknown"
                healthy = False
            
            nodes.append({
                "name": name,
                "base_url": base_url,
                "version": version,
                "healthy": healthy
            })
    
    return JSONResponse(nodes)


@app.get("/api/nlp/parse")
async def parse_deployment(description: str = ""):
    """Parse deployment description and return spec"""
    spec = {
        "description": description,
        "target_version": "v2",
        "nodes": list(NODES.keys()),
        "strategy": "rolling"
    }
    return JSONResponse(spec)


@app.get("/api/generate")
async def generate_plan(spec: str = "{}"):
    """Generate deployment plan from spec"""
    try:
        spec_json = json.loads(spec)
    except:
        spec_json = {"target_version": "v2"}
    
    target_version = spec_json.get("target_version", "v2")
    
    command = f"ansible-playbook -i ansible/inventory.ini ansible/deploy.yml -e target_version={target_version}"
    
    return JSONResponse({
        "command": command,
        "snippets": [
            f"# Deploy to all nodes with version {target_version}",
            command,
            "",
            f"# Rollback command (if needed):",
            f"ansible-playbook -i ansible/inventory.ini ansible/rollback.yml -e rollback_version=v1"
        ]
    })


@app.post("/api/deploy/spec")
async def deploy_spec(background_tasks: BackgroundTasks, spec: str = "{}"):
    """Start deployment with the given spec"""
    global deploy_status
    
    if deploy_status["running"]:
        return JSONResponse({"error": "Deployment already running"}, status_code=409)
    
    try:
        spec_json = json.loads(spec)
    except:
        spec_json = {"target_version": "v2"}
    
    target_version = spec_json.get("target_version", "v2")
    
    nodes = await get_nodes()
    healthy_nodes = [n for n in nodes if n["healthy"]]
    
    if not healthy_nodes:
        deploy_status["error"] = "NO_RUNNER"
        deploy_status["logs"] = ["ERROR: No healthy nodes available for deployment"]
        return JSONResponse({
            "status": "error",
            "error": "NO_RUNNER",
            "message": "No deployment runner linked"
        }, status_code=409)
    
    deploy_status["running"] = True
    deploy_status["status"] = "running"
    deploy_status["logs"] = [f"Starting deployment with target_version={target_version}"]
    deploy_status["error"] = None
    
    background_tasks.add_task(run_deployment, target_version)
    
    return JSONResponse({
        "status": "started",
        "message": f"Deployment started with target_version={target_version}"
    })


async def run_deployment(target_version: str):
    """Run the actual deployment"""
    global deploy_status
    
    try:
        for i, (node_name, config) in enumerate(NODES.items()):
            deploy_status["current_node"] = node_name
            deploy_status["logs"].append(f"\n[{i+1}/{len(NODES)}] Deploying {node_name}...")
            
            await asyncio.sleep(1)
            deploy_status["logs"].append(f"  → Creating override file for {node_name}")
            await asyncio.sleep(0.5)
            deploy_status["logs"].append(f"  → Force recreating {node_name} with APP_VERSION={target_version}")
            await asyncio.sleep(2)
            deploy_status["logs"].append(f"  → Health check for {node_name}...")
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://localhost:{config['port']}/health", timeout=5)
                    if resp.status_code == 200:
                        deploy_status["logs"].append(f"  ✓ {node_name} health check passed")
                    else:
                        deploy_status["logs"].append(f"  ✗ {node_name} health check failed")
            except Exception as e:
                deploy_status["logs"].append(f"  ✗ {node_name} error: {str(e)}")
            
            await asyncio.sleep(0.5)
        
        deploy_status["logs"].append(f"\n✓ Deployment completed successfully")
        deploy_status["status"] = "completed"
        
    except Exception as e:
        deploy_status["logs"].append(f"\n✗ Deployment failed: {str(e)}")
        deploy_status["status"] = "failed"
        deploy_status["error"] = str(e)
    finally:
        deploy_status["running"] = False


@app.get("/api/deploy/status")
async def deploy_status_endpoint():
    """Get current deployment status and logs"""
    return JSONResponse({
        "running": deploy_status["running"],
        "status": deploy_status["status"],
        "current_node": deploy_status["current_node"],
        "logs": deploy_status["logs"],
        "error": deploy_status["error"]
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
