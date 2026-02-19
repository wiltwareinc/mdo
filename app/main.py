# wiltware 2026
# entry point for FastAPI

from fastapi import FastAPI
from app.api import router as api_router

app = FastAPI(title="MDO API", version="0.1.0")

app.include_router(api_router)