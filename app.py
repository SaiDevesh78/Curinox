from fastapi import FastAPI

from routes.scan import router as scan_router
import database

app = FastAPI(
    title="Medicine Authentication API",
    version="1.0.0"
)

app.include_router(scan_router)


@app.get("/")
def home():

    return {
        "status": "Running",
        "message": "Medicine Authentication Backend"
    }
