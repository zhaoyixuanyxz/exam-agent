from app.services.llm_errors import humanize_known_llm_message, tool_error_user_text


def test_humanize_response_format():
    msg = "This response_format type is unavailable now"
    out = humanize_known_llm_message(msg)
    assert out is not None
    assert "重试" in out or "分段" in out


def test_tool_error_user_text():
    s = tool_error_user_text("考点分析失败：", ValueError("random xyz"))
    assert "考点分析失败" in s
    assert "random xyz" in s
