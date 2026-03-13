from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.database.db import init_db
from app.routers.config_router import router as config_router
from app.routers.conversations import router as conversations_router
from app.routers.prompts import router as prompts_router


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="PromptForge MVP", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(conversations_router)
app.include_router(config_router)
app.include_router(prompts_router)


@app.get("/")
def root():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(index_file)


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
