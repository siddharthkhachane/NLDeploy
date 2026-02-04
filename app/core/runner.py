import asyncio
import subprocess
from collections import Counter
from typing import Optional
import logging

from app.core.models import DeploymentSpec
from app.core.store import DeploymentStore
from app.core.nodes import fetch_versions
from app.core.security import get_ansible_command

logger = logging.getLogger(__name__)


async def start_deploy(spec: DeploymentSpec, store: DeploymentStore):
    """
    Start background deployment.
    
    Runs ansible playbook in subprocess, captures logs, and handles rollback.
    
    Args:
        spec: DeploymentSpec with target version
        store: Deployment state store
    """
    store.running = True
    store.logs.append(f"Starting deployment to target_version={spec.target_version}")
    
    try:
        # Get the appropriate ansible command
        ansible_cmd = get_ansible_command()
        if not ansible_cmd:
            raise RuntimeError("ansible-playbook not found in PATH or WSL")
        
        # Fetch current versions and determine rollback version
        store.logs.append("Fetching current node versions...")
        versions = await fetch_versions()
        store.logs.append(f"Current versions: {versions}")
        
        # Compute rollback version (most common current version)
        version_list = [v for v in versions.values() if v != "unknown"]
        if version_list:
            rollback_version = Counter(version_list).most_common(1)[0][0]
        else:
            rollback_version = "v1"
        
        store.rollback = {"version": rollback_version}
        store.logs.append(f"Rollback version set to: {rollback_version}")
        
        # Run ansible playbook
        cmd = [
            ansible_cmd,
            "-i", "ansible/inventory.ini",
            "ansible/deploy.yml",
            f"-e", f"target_version={spec.target_version}"
        ]
        
        store.logs.append(f"Running: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output line by line
        for line in iter(process.stdout.readline, ''):
            if line:
                store.logs.append(line.rstrip())
        
        returncode = process.wait()
        
        if returncode == 0:
            store.logs.append("✓ Deployment completed successfully")
            store.result = {"status": "success", "version": spec.target_version}
        else:
            store.logs.append(f"✗ Deployment failed with exit code {returncode}")
            store.error = f"Deployment failed with exit code {returncode}"
            store.result = {"status": "failed"}
            
            # Auto-rollback on failure
            await run_rollback(rollback_version, store)
    
    except Exception as e:
        store.logs.append(f"✗ Error: {str(e)}")
        store.error = str(e)
        store.result = {"status": "error"}
    
    finally:
        store.running = False


async def run_rollback(rollback_version: str, store: DeploymentStore):
    """
    Run automatic rollback on deployment failure.
    
    Args:
        rollback_version: Version to rollback to
        store: Deployment state store
    """
    store.logs.append(f"\n⟳ Auto-rollback initiated to {rollback_version}")
    
    try:
        cmd = [
            "ansible-playbook",
            "-i", "ansible/inventory.ini",
            "ansible/rollback.yml",
            f"-e", f"rollback_version={rollback_version}"
        ]
        
        store.logs.append(f"Running: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ''):
            if line:
                store.logs.append(line.rstrip())
        
        returncode = process.wait()
        
        if returncode == 0:
            store.logs.append(f"✓ Rollback to {rollback_version} completed")
        else:
            store.logs.append(f"✗ Rollback failed with exit code {returncode}")
    
    except Exception as e:
        store.logs.append(f"✗ Rollback error: {str(e)}")
