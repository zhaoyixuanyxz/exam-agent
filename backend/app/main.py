import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.graph import setup_checkpoint, shutdown_checkpoint
from app.api.chat import router as chat_router
from app.api.exam_papers import router as exam_papers_router
from app.api.knowledge_v23 import router as knowledge_v23_router
from app.api.multi_paper import router as multi_paper_router
from app.api.paper_sets_v23 import router as paper_sets_v23_router
from app.api.question_bank_v23 import router as question_bank_v23_router
from app.api.users_v23 import router as users_v23_router
from app.config import settings
from app.db.init_db import init_db

_REPO_ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all + SQLite 轻量列迁移
    await init_db()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    await setup_checkpoint()
    yield
    await shutdown_checkpoint()


app = FastAPI(title="试卷考点 Agent", lifespan=lifespan)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
_cors_env = (os.getenv("CORS_ORIGINS") or "").strip()
_allow_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins
)
# Same-origin Vercel deploy needs no CORS; preview/custom domains may still hit the API cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(exam_papers_router)
app.include_router(multi_paper_router)
app.include_router(question_bank_v23_router)
app.include_router(knowledge_v23_router)
app.include_router(paper_sets_v23_router)
app.include_router(users_v23_router)
app.mount(
    "/export-files",
    StaticFiles(directory=settings.export_dir.as_posix()),
    name="export-files",
)


def _resolve_static_dir() -> Path | None:
    env = (os.getenv("EXAM_AGENT_STATIC_DIR") or "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    for candidate in (_REPO_ROOT / "public", Path("/app/static")):
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


_STATIC_DIR = _resolve_static_dir()
_SERVE_STATIC = os.getenv("EXAM_AGENT_SERVE_STATIC", "").strip().lower() in (
    "1",
    "true",
    "yes",
) or _STATIC_DIR is not None


def _mount_spa_static() -> None:
    if not _SERVE_STATIC or _STATIC_DIR is None or not _STATIC_DIR.is_dir():
        return

    assets_dir = _STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir.as_posix()), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith(("api/", "api", "export-files/", "export-files")):
            raise HTTPException(404)
        candidate = (_STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(_STATIC_DIR.resolve())
        except ValueError:
            raise HTTPException(404) from None
        if candidate.is_file():
            return FileResponse(candidate)
        index = _STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(404)


_mount_spa_static()
