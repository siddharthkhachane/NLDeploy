# NLDeploy

Built a natural-language deployment system that uses an LLM to translate requests into structured, safe rollout plans, enforced by guardrails and rolling execution.

Tech stack: Python, FastAPI, Ansible, Docker (local server simulation), Jinja (server-side UI), REST APIs, and an LLM for intent interpretation.

Video Demo: https://youtu.be/Sm7j81-H-L0

Latest Update:
Added role based access, environment selection, rollbacks to previous versions and timeline feed
<img width="803" height="800" alt="image" src="https://github.com/user-attachments/assets/f57c819f-c643-49c9-bf8f-cb087e6b1500" />


## Prerequisites

- Docker + Docker Compose
- Python 3.10+
- Ansible (`ansible-playbook`) on PATH or available in WSL

## Run

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start node containers:
```bash
docker compose -f docker/docker-compose.yml up --build -d
```

3. Start UI/API:
```bash
uvicorn app.main:app --reload --port 8000
```

4. Open:
```text
http://localhost:8000
```

## Check

1. Verify nodes:
```bash
curl http://localhost:18081/health
curl http://localhost:18082/health
curl http://localhost:18083/health
```

2. Try a normal deploy in UI:
- Enter `Deploy v2 to all nodes`
- Click `Generate Plan`, then `Deploy`
- Watch timeline advance through canary and rollout

3. Test rollback demo:
- Enable `Simulate failure on node2`
- Run `Deploy v3 to all nodes`
- Confirm logs show failure and auto-rollback

4. Test risk guardrail:
- Enter `Stop all nodes`
- Generate plan, observe risk checks
- Execute is blocked unless `I confirm this risky command` is checked

## One-Command Demo (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
```

This script starts containers, runs API tests, and prints the key endpoints to open/check.
Deployed Version: v1
