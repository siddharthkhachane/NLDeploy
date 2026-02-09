import json
import subprocess
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.generate import generate_artifacts
from app.core.models import CommandSpec, DeploymentSpec
from app.core.nlp import parse_deploy_text
from app.core.nodes import NODES
from app.core.runner import start_deploy
from app.core.security import (
    assess_command_risk,
    get_ansible_command,
    runner_available,
    validate_command_execution,
    validate_version_string,
)
from app.core.store import DeploymentStore, get_store, reset_store

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ParseRequest(BaseModel):
    text: str


class DeploySpecRequest(BaseModel):
    spec: DeploymentSpec


class CommandSpecRequest(BaseModel):
    spec: CommandSpec


class PreviewRequest(BaseModel):
    spec_type: str
    spec: dict[str, Any]


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/nodes")
async def get_nodes():
    nodes = []
    async with httpx.AsyncClient() as client:
        for name, config in NODES.items():
            base_url = f"http://localhost:{config['port']}"
            try:
                version_resp = await client.get(f"{base_url}/version", timeout=2)
                version = (
                    version_resp.json().get("version", "unknown")
                    if version_resp.status_code == 200
                    else "unknown"
                )
                health_resp = await client.get(f"{base_url}/health", timeout=2)
                healthy = health_resp.status_code == 200
            except Exception:
                version = "unknown"
                healthy = False

            nodes.append(
                {
                    "name": name,
                    "base_url": base_url,
                    "version": version,
                    "healthy": healthy,
                }
            )
    return JSONResponse(nodes)


@app.post("/api/nlp/parse")
async def parse_deployment_endpoint(request: ParseRequest):
    try:
        spec = parse_deploy_text(request.text)
        result = spec.model_dump()
        result["spec_type"] = "deployment" if isinstance(spec, DeploymentSpec) else "command"
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/generate")
async def generate_plan(spec: str = "{}"):
    try:
        spec_json = json.loads(spec)
        spec_obj = DeploymentSpec(**spec_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JSONResponse(generate_artifacts(spec_obj))


@app.post("/api/plan/preview")
async def preview_plan(request: PreviewRequest):
    if request.spec_type == "deployment":
        spec = DeploymentSpec(**request.spec)
        artifacts = generate_artifacts(spec)
        return JSONResponse(
            {
                "spec_type": "deployment",
                "summary": f"Deploy {spec.target_version} with canary-first rollout",
                "impacted_nodes": artifacts["impacted_nodes"],
                "exact_commands": [artifacts["command"]],
                "risk_checks": artifacts["risk_checks"],
                "stages": artifacts["stages"],
            }
        )

    if request.spec_type == "command":
        spec = CommandSpec(**request.spec)
        requires_confirmation, risk_reason = assess_command_risk(spec)
        return JSONResponse(
            {
                "spec_type": "command",
                "summary": f"{spec.command_type} on {', '.join(spec.target_nodes)}",
                "impacted_nodes": spec.target_nodes,
                "exact_commands": [
                    f"ansible-playbook ansible/{spec.command_type}.yml -i ansible/inventory.ini -l {','.join(spec.target_nodes)}"
                ],
                "risk_checks": [risk_reason] if risk_reason else ["No high-risk checks triggered."],
                "stages": ["parse", "plan", "execute", "verify"],
                "requires_confirmation": requires_confirmation,
            }
        )

    raise HTTPException(status_code=400, detail="spec_type must be deployment or command")


@app.post("/api/deploy/spec")
async def deploy_with_spec(background_tasks: BackgroundTasks, request: DeploySpecRequest):
    if not runner_available():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_RUNNER",
                "message": "Ansible runner not available. Install ansible-playbook on PATH or in WSL.",
            },
        )

    spec = request.spec
    if not validate_version_string(spec.target_version):
        raise HTTPException(status_code=400, detail="Invalid version format")

    reset_store()
    store = get_store()
    background_tasks.add_task(start_deploy, spec, store)
    return JSONResponse(
        {
            "status": "started",
            "run_id": store.run_id,
            "message": f"Deployment started with target_version={spec.target_version}",
        }
    )


async def execute_command(command_spec: CommandSpec, store: DeploymentStore) -> None:
    try:
        validate_command_execution(command_spec)
        store.running = True
        store.logs = []
        store.current_stage = "execute"
        store.timeline = [{"stage": "parse", "detail": "Command accepted"}]

        ansible_cmd = get_ansible_command()
        if not ansible_cmd:
            raise RuntimeError("ansible-playbook not found in PATH or WSL")

        target_filter = ",".join(command_spec.target_nodes)
        playbook = f"ansible/{command_spec.command_type}.yml"
        cmd = [*ansible_cmd, playbook, "-i", "ansible/inventory.ini", "-l", target_filter]
        cmd.extend(["-e", f"target_nodes={target_filter}"])

        store.timeline.append({"stage": "execute", "detail": "Running ansible command"})
        store.logs.append(f"Executing {command_spec.command_type} on {', '.join(command_spec.target_nodes)}")
        store.logs.append(f"Running: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in iter(process.stdout.readline, ""):
            if line:
                store.logs.append(line.rstrip())

        returncode = process.wait()
        store.current_stage = "verify"
        if returncode == 0:
            store.result = {"status": "success"}
            store.timeline.append({"stage": "verify", "detail": "Command completed successfully"})
            store.logs.append("Command completed successfully")
        else:
            store.result = {"status": "failed"}
            store.error = f"Command exited with code {returncode}"
            store.timeline.append({"stage": "failed", "detail": store.error})
            store.logs.append("Command failed")

    except ValueError as e:
        store.result = {"status": "blocked"}
        store.error = str(e)
        store.timeline.append({"stage": "blocked", "detail": str(e)})
        store.logs.append(f"Blocked: {str(e)}")
    except Exception as e:
        store.result = {"status": "failed"}
        store.error = str(e)
        store.timeline.append({"stage": "failed", "detail": str(e)})
        store.logs.append(f"Error executing command: {str(e)}")
    finally:
        store.running = False


@app.post("/api/command/execute")
async def execute_command_endpoint(background_tasks: BackgroundTasks, request: CommandSpecRequest):
    if not runner_available():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_RUNNER",
                "message": "Ansible runner not available. Install ansible-playbook on PATH or in WSL.",
            },
        )

    reset_store()
    store = get_store()
    background_tasks.add_task(execute_command, request.spec, store)
    return JSONResponse(
        {
            "status": "started",
            "run_id": store.run_id,
            "command_type": request.spec.command_type,
            "target_nodes": request.spec.target_nodes,
            "message": f"Command '{request.spec.command_type}' started",
        }
    )


@app.get("/api/deploy/status")
async def deploy_status():
    store = get_store()
    return JSONResponse(
        {
            "running": store.running,
            "run_id": store.run_id,
            "logs": store.logs,
            "result": store.result,
            "rollback": store.rollback,
            "error": store.error,
            "current_stage": store.current_stage,
            "timeline": store.timeline,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
