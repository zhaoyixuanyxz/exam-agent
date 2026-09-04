import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env (not CWD), so uvicorn from any working directory still gets the key.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


def _running_serverless() -> bool:
    if os.getenv("VERCEL", "").strip():
        return True
    return os.getenv("EXAM_AGENT_SERVERLESS", "").strip().lower() in ("1", "true", "yes")


def _deepseek_key_from_backend_env_file() -> str | None:
    """Read DEEPSEEK_API_KEY from backend/.env only; ignores OS env for this key."""
    if not _ENV_FILE.is_file():
        return None
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("DEEPSEEK_API_KEY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            return val if val else None
    return None


def _default_data_dir() -> Path:
    env_data = (os.getenv("DATA_DIR") or "").strip()
    if env_data:
        p = Path(env_data)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Vercel / serverless: only /tmp is writable across invocations on the same instance.
    if _running_serverless():
        p = Path("/tmp/exam-agent-data")
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(__file__).resolve().parents[2] / "data"


# 官方单次输出上限（https://api-docs.deepseek.com/quick_start/pricing），用于钳制请求中的 max_tokens。
DEEPSEEK_CHAT_MAX_OUTPUT_TOKENS = 8192
DEEPSEEK_REASONER_MAX_OUTPUT_TOKENS = 65536


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 分块练习出题期望的 max_tokens；实际请求见 effective_practice_max_output_tokens（按模型钳制）。
    practice_max_output_tokens: int = 8192
    # 批量考点出题工具单次 items_json 最多条数（防单次请求过久/超时）。
    practice_batch_max_knowledge_points: int = 8
    # 分难度出题 temperature（朱老师风格迭代，可通过 env 微调）
    practice_difficulty_temperature_easy: float = 0.15
    practice_difficulty_temperature_medium: float = 0.25
    practice_difficulty_temperature_hard: float = 0.30

    data_dir: Path = _default_data_dir()
    kaiti_font_path: str | None = None

    max_upload_bytes: int = 50 * 1024 * 1024

    # 练习 PDF：可选内联 mathtext 小图（题干/解析中含 $...$ 时尝试栅格嵌入）
    practice_pdf_inline_mathtext: bool = False
    # 生成分块练习 PDF 时是否额外写出配图诊断 JSON（与 pdf 同目录）
    practice_pdf_write_figure_diagnostics: bool = False

    # LaTeX 子系统：off Unicode；katex Playwright+CDN；tex pdflatex/xelatex+PyMuPDF
    # Vercel 无 Chromium/TeX，强制保持 off（可用 env 覆盖仅限本地）。
    practice_pdf_latex_renderer: Literal["off", "katex", "tex"] = "off"
    practice_pdf_latex_timeout_sec: float = 25.0
    practice_pdf_latex_cache_dir: str = "cache/formula_png"
    practice_pdf_latex_dpi: int = 160
    practice_pdf_latex_fallback: Literal["flatten", "placeholder"] = "flatten"
    practice_pdf_latex_max_inner_chars: int = 8000
    # 分流：满足任一条件则尝试 LaTeX 渲染（renderer 非 off 时）；min_inner_len=0 表示仅用结构特征
    practice_pdf_latex_router_min_inner_len: int = 120
    practice_pdf_latex_router_max_brace_depth: int = 8
    practice_pdf_latex_katex_css_url: str = (
        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
    )
    practice_pdf_latex_katex_js_url: str = (
        "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
    )
    practice_pdf_latex_pdflatex_cmd: str = "pdflatex"
    practice_pdf_latex_xelatex_cmd: str = "xelatex"
    practice_pdf_write_formula_diagnostics: bool = False

    @property
    def upload_dir(self) -> Path:
        p = self.data_dir / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def export_dir(self) -> Path:
        p = self.data_dir / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def practice_pdf_latex_cache_path(self) -> Path:
        p = (self.data_dir / (self.practice_pdf_latex_cache_dir or "cache/formula_png")).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "app.db"

    @property
    def checkpoint_db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "checkpoints.db"

    @property
    def effective_practice_max_output_tokens(self) -> int:
        """出题 API 的 max_tokens：不超过当前模型官方单次输出上限（chat 8K / reasoner 64K）。"""
        raw = max(1, int(self.practice_max_output_tokens))
        m = (self.deepseek_model or "").lower()
        if "reasoner" in m:
            return min(raw, DEEPSEEK_REASONER_MAX_OUTPUT_TOKENS)
        return min(raw, DEEPSEEK_CHAT_MAX_OUTPUT_TOKENS)

    def require_deepseek_api_key(self) -> str:
        """Non-empty trimmed key for outbound API calls; raises if missing or placeholder."""
        file_key = _deepseek_key_from_backend_env_file()
        merged = file_key if file_key is not None else (self.deepseek_api_key or "")
        key = merged.strip().strip('"').strip("'")
        if not key:
            raise ValueError("DEEPSEEK_API_KEY_MISSING")
        bad = {
            "missing-key",
            "dummy",
            "your-api-key",
            "changeme",
            "sk-xxx",
            "sk-test",
        }
        if key.lower() in bad:
            raise ValueError("DEEPSEEK_API_KEY_PLACEHOLDER")
        return key


settings = Settings()
