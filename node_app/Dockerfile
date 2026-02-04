FROM python:3.9-slim

WORKDIR /app

RUN pip install fastapi uvicorn

COPY server.py .

EXPOSE 8080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
