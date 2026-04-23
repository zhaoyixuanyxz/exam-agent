from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agent.graph import setup_checkpoint, shutdown_checkpoint
from app.api.chat import router as chat_router
from app.api.exam_papers import router as exam_papers_router
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
app.mount(
    "/export-files",
    StaticFiles(directory=settings.export_dir.as_posix()),
    name="export-files",
)
