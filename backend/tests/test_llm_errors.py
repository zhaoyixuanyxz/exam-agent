from app.services.llm_errors import user_message_for_llm_error


def test_user_message_401():
    msg = user_message_for_llm_error(
        RuntimeError(
            "Error code: 401 - {'error': {'message': 'invalid', 'type': 'authentication_error'}}"
        )
    )
    assert "401" in msg or "鉴权" in msg
    assert "DEEPSEEK_API_KEY" in msg or "sk-" in msg


def test_user_message_missing_key_marker():
    msg = user_message_for_llm_error(ValueError("DEEPSEEK_API_KEY_MISSING"))
    assert "未配置" in msg or "DEEPSEEK_API_KEY" in msg
