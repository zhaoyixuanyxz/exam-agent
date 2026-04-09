from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env (not CWD), so uvicorn from any working directory still gets the key.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


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

    data_dir: Path = _default_data_dir()
    kaiti_font_path: str | None = None

    max_upload_bytes: int = 50 * 1024 * 1024

    # 练习 PDF：可选内联 mathtext 小图（题干/解析中含 $...$ 时尝试栅格嵌入）
    practice_pdf_inline_mathtext: bool = False
    # 生成分块练习 PDF 时是否额外写出配图诊断 JSON（与 pdf 同目录）
    practice_pdf_write_figure_diagnostics: bool = False

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
