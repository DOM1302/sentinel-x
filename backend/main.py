from fastapi import FastAPI

app = FastAPI(
    title="Sentinel-X API",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "service": "sentinel-x-backend",
        "status": "running"
    }

@app.get("/health")
def health():
    return {
        "status": "ok"
    }
