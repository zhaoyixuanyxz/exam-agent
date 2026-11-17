from unittest.mock import patch

from app.config import Settings, settings
from app.services.vision_read import read_image_text


def test_read_image_text_uses_deepseek_vision_model_setting():
    """Vision path must use deepseek_vision_model (may match deepseek_model when both are flash)."""
    msg = type("Msg", (), {"content": "第一题 二次函数"})()
    vision_model = "deepseek-vision-wire-check"
    with (
        patch("app.services.vision_read.ChatOpenAI") as chat,
        patch.object(Settings, "require_deepseek_api_key", return_value="sk-unit-not-placeholder"),
        patch.object(settings, "deepseek_vision_model", vision_model),
    ):
        chat.return_value.invoke.return_value = msg
        out = read_image_text(b"\x89PNG\r\n")
    model = chat.call_args.kwargs["model"]
    assert out == "第一题 二次函数"
    assert model == vision_model
    assert model != "deepseek-chat"
