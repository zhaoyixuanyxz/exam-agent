from unittest.mock import patch

from app.config import Settings, settings
from app.services.vision_read import read_image_text


def test_read_image_text_uses_deepseek_flash_not_chat():
    msg = type("Msg", (), {"content": "第一题 二次函数"})()
    with (
        patch("app.services.vision_read.ChatOpenAI") as chat,
        patch.object(Settings, "require_deepseek_api_key", return_value="sk-unit-not-placeholder"),
    ):
        chat.return_value.invoke.return_value = msg
        out = read_image_text(b"\x89PNG\r\n")
    model = chat.call_args.kwargs["model"]
    assert out == "第一题 二次函数"
    assert model == settings.deepseek_vision_model
    assert model == "deepseek-flash"
    assert model != "deepseek-chat"
    assert chat.call_args.kwargs["model"] != settings.deepseek_model
