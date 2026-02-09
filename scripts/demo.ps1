$ErrorActionPreference = "Stop"

Write-Host "[1/4] Installing Python deps..."
pip install -r requirements.txt

Write-Host "[2/4] Starting docker nodes..."
docker compose -f docker/docker-compose.yml up --build -d

Write-Host "[3/4] Running tests..."
pytest -q

Write-Host "[4/4] Starting API..."
Write-Host "Open: http://localhost:8000"
Write-Host "Run in separate shell: uvicorn app.main:app --reload --port 8000"
