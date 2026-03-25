from pathlib import Path

from app.config import settings


def resolve_kaiti_font() -> Path:
    if settings.kaiti_font_path:
        p = Path(settings.kaiti_font_path)
        if p.is_file():
            return p
    candidates = [
        Path(r"C:\Windows\Fonts\simkai.ttf"),
        Path(r"C:\Windows\Fonts\STKAITI.TTF"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simfang.ttf"),
        Path(r"C:\Windows\Fonts\STXINGKA.TTF"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "未找到楷体字体。请设置环境变量 KAITI_FONT_PATH 指向 .ttf 文件，或在 Windows 安装中文字体。"
    )
