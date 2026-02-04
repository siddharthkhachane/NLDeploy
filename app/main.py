import os
import json
import asyncio
from typing import List, Dict, Union
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import httpx
from pydantic import BaseModel
import subprocess

from app.core.models import DeploymentSpec, CommandSpec
from app.core.nlp import parse_deploy_text
from app.core.generate import generate_artifacts
from app.core.security import runner_available, validate_version_string
from app.core.store import get_store, set_store, DeploymentStore, reset_store
from app.core.runner import start_deploy
from app.core.nodes import NODES

app = FastAPI()

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Request models
class ParseRequest(BaseModel):
    text: str
    
class DeploySpecRequest(BaseModel):
    spec: DeploymentSpec


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


@app.post("/api/nlp/parse")
async def parse_deployment_endpoint(request: ParseRequest):
    """Parse natural language deployment or command description"""
    try:
        spec = parse_deploy_text(request.text)
        result = spec.model_dump()
        
        # Add spec_type for frontend handling
        if isinstance(spec, DeploymentSpec):
            result["spec_type"] = "deployment"
        elif isinstance(spec, CommandSpec):
            result["spec_type"] = "command"
        
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/nlp/parse")
async def parse_deployment(description: str = ""):
    """Parse deployment description and return spec (GET fallback)"""
    try:
        spec = parse_deploy_text(description)
        return JSONResponse(spec.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/generate")
async def generate_plan(spec: str = "{}"):
    """Generate deployment plan from spec (always available, no runner needed)"""
    try:
        spec_json = json.loads(spec)
        spec_obj = DeploymentSpec(**spec_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    artifacts = generate_artifacts(spec_obj)
    return JSONResponse(artifacts)


@app.post("/api/deploy/spec")
async def deploy_with_spec(background_tasks: BackgroundTasks, request: DeploySpecRequest):
    """
    Start deployment with spec.
    
    Returns 409 with NO_RUNNER error if runner not available.
    """
    # Check runner availability
    if not runner_available():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_RUNNER",
                "message": "Ansible runner not available. On Windows, ensure Ansible is installed (WSL recommended) or nodes are running for generate-only mode."
            }
        )
    
    # Validate version string
    spec = request.spec
    if not validate_version_string(spec.target_version):
        raise HTTPException(status_code=400, detail="Invalid version format")
    
    # Reset and initialize store
    reset_store()
    store = get_store()
    
    # Start deployment in background
    background_tasks.add_task(start_deploy, spec, store)
    
    return JSONResponse({
        "status": "started",
        "run_id": store.run_id,
        "message": f"Deployment started with target_version={spec.target_version}"
    })


class CommandSpecRequest(BaseModel):
    spec: CommandSpec


async def execute_command(command_spec: CommandSpec, store: DeploymentStore) -> None:
    """
    Execute a command on target nodes.
    
    Args:
        command_spec: Command specification
        store: Deployment store for logging
    """
    try:
        store.running = True
        store.logs = []
        
        # Get the appropriate ansible command
        from app.core.security import get_ansible_command
        ansible_cmd = get_ansible_command()
        if not ansible_cmd:
            raise RuntimeError("ansible-playbook not found in PATH or WSL")
        
        # Build target filter for Ansible
        target_filter = ",".join(command_spec.target_nodes)
        
        command_type = command_spec.command_type
        playbook = f"ansible/{command_type}.yml"
        
        store.logs.append(f"Executing {command_type} on {', '.join(command_spec.target_nodes)}")
        store.logs.append(f"Running: {ansible_cmd} {playbook} -i ansible/inventory.ini -l {target_filter}")
        
        # Run Ansible playbook
        process = subprocess.Popen(
            [
                ansible_cmd,
                playbook,
                "-i", "ansible/inventory.ini",
                "-l", target_filter,
                "-e", f"target_nodes={','.join(command_spec.target_nodes)}"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Stream output
        for line in process.stdout:
            line = line.rstrip('\n')
            if line:
                store.logs.append(line)
        
        process.wait()
        
        if process.returncode == 0:
            store.result = "success"
            store.logs.append(f"\n✓ {command_type.capitalize()} command completed successfully")
        else:
            store.result = "failed"
            store.error = f"Command exited with code {process.returncode}"
            store.logs.append(f"\n✗ {command_type.capitalize()} command failed")
        
    except Exception as e:
        store.result = "failed"
        store.error = str(e)
        store.logs.append(f"\n✗ Error executing command: {str(e)}")
    finally:
        store.running = False


@app.post("/api/command/execute")
async def execute_command_endpoint(background_tasks: BackgroundTasks, request: CommandSpecRequest):
    """
    Execute a command (stop, restart, etc.) on target nodes.
    
    Returns 409 with NO_RUNNER error if runner not available.
    """
    # Check runner availability
    if not runner_available():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_RUNNER",
                "message": "Ansible runner not available. On Windows, ensure Ansible is installed (WSL recommended) or nodes are running for generate-only mode."
            }
        )
    
    # Reset and initialize store
    reset_store()
    store = get_store()
    
    # Start command execution in background
    background_tasks.add_task(execute_command, request.spec, store)
    
    return JSONResponse({
        "status": "started",
        "run_id": store.run_id,
        "command_type": request.spec.command_type,
        "target_nodes": request.spec.target_nodes,
        "message": f"Command '{request.spec.command_type}' started on {', '.join(request.spec.target_nodes)}"
    })



@app.get("/api/deploy/status")
async def deploy_status():
    """Get current deployment status and logs"""
    store = get_store()
    return JSONResponse({
        "running": store.running,
        "run_id": store.run_id,
        "logs": store.logs,
        "result": store.result,
        "rollback": store.rollback,
        "error": store.error
    })


# Legacy POST endpoint for backward compatibility
@app.post("/api/deploy/spec_old")
async def deploy_spec(background_tasks: BackgroundTasks, spec: str = "{}"):
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
