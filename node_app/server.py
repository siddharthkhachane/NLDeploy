import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

# Read environment variables
NODE_NAME = os.getenv("NODE_NAME", "node")
APP_VERSION = os.getenv("APP_VERSION", "v1")


@app.get("/")
async def root():
    """Root endpoint returning node information"""
    return JSONResponse({
        "node": NODE_NAME,
        "version": APP_VERSION
    })


@app.get("/health")
async def health():
    """Health check endpoint"""
    return JSONResponse({"status": "ok"}), 200


@app.get("/version")
async def version():
    """Version endpoint"""
    return JSONResponse({"version": APP_VERSION})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
