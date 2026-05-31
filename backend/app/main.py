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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Docker / VPS：单容器托管前端静态资源（见 Dockerfile、docker-compose.yml）
_SERVE_STATIC = os.getenv("EXAM_AGENT_SERVE_STATIC", "").strip() in ("1", "true", "yes")
_STATIC_DIR = Path(os.getenv("EXAM_AGENT_STATIC_DIR", "/app/static"))


def _mount_spa_static() -> None:
    if not _SERVE_STATIC or not _STATIC_DIR.is_dir():
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
