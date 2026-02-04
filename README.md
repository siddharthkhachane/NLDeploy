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

