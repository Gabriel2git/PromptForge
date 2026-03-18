from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

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


def _asset_version(filename: str) -> str:
    asset = FRONTEND_DIR / "assets" / filename
    if not asset.exists():
        return "dev"
    return str(int(asset.stat().st_mtime))


@app.middleware("http")
async def disable_frontend_cache(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in {"/", "/assets/app.js", "/assets/style.css"}:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(conversations_router)
app.include_router(config_router)
app.include_router(prompts_router)


@app.get("/")
def root():
    index_file = FRONTEND_DIR / "index.html"
    html = index_file.read_text(encoding="utf-8")
    html = html.replace('/assets/style.css"', f'/assets/style.css?v={_asset_version("style.css")}"')
    html = html.replace('/assets/app.js"', f'/assets/app.js?v={_asset_version("app.js")}"')
    return HTMLResponse(content=html)


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
