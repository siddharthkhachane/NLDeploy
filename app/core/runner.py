import subprocess
from collections import Counter
import logging
from typing import Optional

from app.core.models import DeploymentSpec
from app.core.store import DeploymentStore, add_activity
from app.core.nodes import fetch_versions
from app.core.security import get_ansible_command

logger = logging.getLogger(__name__)


def _append_stage(store: DeploymentStore, stage: str, detail: str) -> None:
    store.current_stage = stage
    store.timeline.append({"stage": stage, "detail": detail})
    store.logs.append(f"[{stage}] {detail}")


async def start_deploy(
    spec: DeploymentSpec,
    store: DeploymentStore,
    actor: str = "unknown",
    role: str = "admin",
    environment: str = "dev",
):
    """
    Start background deployment.

    Runs ansible playbook in subprocess, captures logs, and handles rollback.
    """
    store.running = True
    _append_stage(store, "parse", f"Accepted spec for target_version={spec.target_version}")
    add_activity(
        {
            "run_id": store.run_id,
            "type": "deploy",
            "actor": actor,
            "role": role,
            "environment": environment,
            "status": "started",
            "detail": f"Deploy requested for {spec.target_version}",
        }
    )

    try:
        ansible_cmd = get_ansible_command()
        if not ansible_cmd:
            raise RuntimeError("ansible-playbook not found in PATH or WSL")

        _append_stage(store, "plan", "Collecting current versions and preparing rollback")
        versions = await fetch_versions()
        store.logs.append(f"Current versions: {versions}")

        version_list = [v for v in versions.values() if v != "unknown"]
        rollback_version = Counter(version_list).most_common(1)[0][0] if version_list else "v1"
        store.rollback = {"version": rollback_version}
        store.logs.append(f"Rollback version set to: {rollback_version}")

        cmd = [
            *ansible_cmd,
            "-i", "ansible/inventory.ini",
            "ansible/deploy.yml",
            "-e", f"target_version={spec.target_version}",
        ]
        if spec.failure_injection_node:
            cmd.extend(["-e", f"force_fail_node={spec.failure_injection_node}"])

        _append_stage(store, "canary", "Starting canary deployment on first node")
        store.logs.append(f"Running: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in iter(process.stdout.readline, ""):
            if not line:
                continue
            clean_line = line.rstrip()
            lower = clean_line.lower()
            if "play [canary deploy" in lower:
                _append_stage(store, "canary", "Canary phase in progress")
            elif "play [rolling deploy" in lower:
                _append_stage(store, "rollout", "Promoting canary and rolling to remaining nodes")
            elif "health check" in lower:
                _append_stage(store, "verify", "Running post-deploy verification")
            store.logs.append(clean_line)

        returncode = process.wait()

        if returncode == 0:
            _append_stage(store, "verify", "Deployment completed successfully")
            store.result = {"status": "success", "version": spec.target_version}
            add_activity(
                {
                    "run_id": store.run_id,
                    "type": "deploy",
                    "actor": actor,
                    "role": role,
                    "environment": environment,
                    "status": "success",
                    "detail": f"Deployment completed to {spec.target_version}",
                }
            )
        else:
            _append_stage(store, "rollback", f"Deployment failed with exit code {returncode}")
            store.error = f"Deployment failed with exit code {returncode}"
            store.result = {"status": "failed"}
            add_activity(
                {
                    "run_id": store.run_id,
                    "type": "deploy",
                    "actor": actor,
                    "role": role,
                    "environment": environment,
                    "status": "failed",
                    "detail": store.error,
                }
            )
            await run_rollback(
                rollback_version=rollback_version,
                store=store,
                actor=actor,
                role=role,
                environment=environment,
                trigger="auto",
            )

    except Exception as e:
        _append_stage(store, "failed", f"Error: {str(e)}")
        store.error = str(e)
        store.result = {"status": "error"}
        add_activity(
            {
                "run_id": store.run_id,
                "type": "deploy",
                "actor": actor,
                "role": role,
                "environment": environment,
                "status": "error",
                "detail": str(e),
            }
        )
    finally:
        store.running = False


async def run_rollback(
    rollback_version: str,
    store: DeploymentStore,
    actor: str = "system",
    role: str = "system",
    environment: str = "dev",
    trigger: str = "auto",
):
    """
    Run automatic rollback on deployment failure.
    """
    _append_stage(store, "rollback", f"{trigger.capitalize()} rollback initiated to {rollback_version}")
    add_activity(
        {
            "run_id": store.run_id,
            "type": "rollback",
            "actor": actor,
            "role": role,
            "environment": environment,
            "status": "started",
            "detail": f"{trigger} rollback to {rollback_version}",
        }
    )

    try:
        ansible_cmd = get_ansible_command()
        if not ansible_cmd:
            raise RuntimeError("ansible-playbook not found in PATH or WSL")

        cmd = [
            *ansible_cmd,
            "-i", "ansible/inventory.ini",
            "ansible/rollback.yml",
            "-e", f"rollback_version={rollback_version}",
        ]

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
        if returncode == 0:
            _append_stage(store, "rollback", f"Rollback to {rollback_version} completed")
            add_activity(
                {
                    "run_id": store.run_id,
                    "type": "rollback",
                    "actor": actor,
                    "role": role,
                    "environment": environment,
                    "status": "success",
                    "detail": f"Rollback to {rollback_version} completed",
                }
            )
        else:
            _append_stage(store, "failed", f"Rollback failed with exit code {returncode}")
            add_activity(
                {
                    "run_id": store.run_id,
                    "type": "rollback",
                    "actor": actor,
                    "role": role,
                    "environment": environment,
                    "status": "failed",
                    "detail": f"Rollback failed with exit code {returncode}",
                }
            )

    except Exception as e:
        _append_stage(store, "failed", f"Rollback error: {str(e)}")
        add_activity(
            {
                "run_id": store.run_id,
                "type": "rollback",
                "actor": actor,
                "role": role,
                "environment": environment,
                "status": "error",
                "detail": f"Rollback error: {str(e)}",
            }
        )


async def run_manual_rollback_latest(
    store: DeploymentStore,
    actor: str,
    role: str,
    environment: str,
) -> Optional[str]:
    """
    Trigger rollback to the most recent rollback version in store.
    Returns selected rollback version, or None if unavailable.
    """
    rollback = store.rollback or {}
    rollback_version = rollback.get("version")
    if not rollback_version:
        return None
    store.running = True
    try:
        await run_rollback(
            rollback_version=rollback_version,
            store=store,
            actor=actor,
            role=role,
            environment=environment,
            trigger="manual",
        )
    finally:
        store.running = False
    return rollback_version
