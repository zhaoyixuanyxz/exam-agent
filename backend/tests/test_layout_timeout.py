from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.layout_timeout import (
    TIMEOUT_MESSAGE,
    assistant_text_after_layout_timeout,
    is_connection_timeout,
    run_layout_write,
    user_text_for_layout_timeout,
)


def test_timeout_message_is_exact_sentence_without_secrets():
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
    assert "Traceback" not in TIMEOUT_MESSAGE
    assert "sk-" not in TIMEOUT_MESSAGE


def test_is_connection_timeout_matches_interrupts_only():
    assert is_connection_timeout(TimeoutError()) is True
    assert is_connection_timeout(TimeoutError("timed out")) is True
    assert is_connection_timeout(ConnectionResetError()) is True
    assert is_connection_timeout(ConnectionError("Connection refused")) is True
    assert is_connection_timeout(Exception("ConnectError: failed")) is True
    assert is_connection_timeout(ValueError("nope")) is False
    assert is_connection_timeout(ValueError("KaiTi missing")) is False


def test_user_text_for_layout_timeout_is_sentence_or_none():
    assert user_text_for_layout_timeout(TimeoutError("timed out")) == TIMEOUT_MESSAGE
    assert user_text_for_layout_timeout(ValueError("KaiTi missing")) is None


def test_run_layout_write_timeout_keeps_existing_file(tmp_path: Path):
    kept = tmp_path / "考点说明.pdf"
    kept.write_bytes(b"%PDF-1.4 color")

    def boom() -> None:
        raise ConnectionResetError("reset")

    assert run_layout_write(boom) == TIMEOUT_MESSAGE
    assert kept.read_bytes() == b"%PDF-1.4 color"


def test_run_layout_write_other_errors_still_raise():
    def boom() -> None:
        raise ValueError("KaiTi missing")

    try:
        run_layout_write(boom)
    except ValueError as exc:
        assert "KaiTi" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_assistant_text_after_layout_timeout_overrides_paraphrase():
    msgs = [
        HumanMessage(content="出练习"),
        AIMessage(content=""),
        ToolMessage(content=TIMEOUT_MESSAGE, tool_call_id="1"),
        AIMessage(content="网络好像不太好，我们换个说法再试。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) == TIMEOUT_MESSAGE


def test_assistant_text_after_layout_timeout_none_when_success():
    msgs = [
        ToolMessage(content="成功：练习已生成，请在界面「生成文件」中下载。", tool_call_id="1"),
        AIMessage(content="练习卷已经在生成文件里了。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) is None
