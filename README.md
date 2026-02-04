# NLDeploy

## Step 1: Docker Nodes (3 Linux Containers)

This project implements a multi-node deployment system with FastAPI servers running in Docker containers.

### Prerequisites
- Docker
- Docker Compose

### Quick Start

Build and start the containers:
```bash
docker compose -f docker/docker-compose.yml up --build
```

### Testing the Services

Check node1:
```bash
curl localhost:18081/version
```

Check health:
```bash
curl localhost:18081/health
```

### Available Endpoints

Each node exposes:
- `GET /` - Returns node name and version
- `GET /health` - Health check endpoint
- `GET /version` - Returns app version

Deployed Version: v1

---

## Step 2: Ansible Rolling Deploy Playbook

Rolling deployment with docker compose override files per service.

### Prerequisites
- Ansible installed
- Docker and Docker Compose running
- All nodes running

### Usage

Deploy a new version to all nodes (one at a time):
```bash
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml -e target_version=v2
```

This will:
1. Create a compose override file for each service with the new APP_VERSION
2. Force recreate only that service with the new version
3. Run health checks with retries (30 times with 0.5s delay)
4. Update README with deployed version

### Inventory File

The `ansible/inventory.ini` defines three hosts with:
- `service_name`: name of the docker service
- `host_port`: port to health check on

### Group Variables

The `ansible/group_vars/all.yml` defines:
- `health_path`: `/health` endpoint path
- `retries`: 30 attempts for health check
- `delay_sec`: 0.5 seconds between retries

---

## Step 3: Ansible Rollback Playbook

Rollback to a previous version.

### Usage

Rollback all nodes to a previous version:
```bash
ansible-playbook -i ansible/inventory.ini ansible/rollback.yml -e rollback_version=v1
```

This will:
1. Create a compose override file for each service with the rollback APP_VERSION
2. Force recreate only that service with the rollback version
3. Run health checks with retries
4. Update README with rollback version

### Rollback Strategy

Similar to deploy playbook but uses `rollback_version` variable to target a specific version to revert to.

