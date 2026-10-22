from app.services.page_text import (
    EMPTY_PAPER_MESSAGE,
    MAX_VISION_ATTEMPTS,
    page_text_is_sparse,
    read_sparse_page,
)


def test_page_text_is_sparse_needs_four_cjk_or_letters():
    assert page_text_is_sparse("") is True
    assert page_text_is_sparse("abc") is True
    assert page_text_is_sparse("一二三") is True
    assert page_text_is_sparse("第一题二次函数") is False
    assert page_text_is_sparse("abcd") is False


def test_read_sparse_page_returns_text_on_first_good_read():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        return "第一题 二次函数顶点"

    assert read_sparse_page(once) == "第一题 二次函数顶点"
    assert calls["n"] == 1


def test_read_sparse_page_retries_then_merges():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("timed out")
        return "第2题 几何面积"

    assert read_sparse_page(once) == "第2题 几何面积"
    assert calls["n"] == 3


def test_read_sparse_page_retries_timeout_error():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("timed out")
        return "第3题 函数图像"

    assert read_sparse_page(once) == "第3题 函数图像"
    assert calls["n"] == 3


def test_read_sparse_page_reraises_missing_api_key_without_extra_loops():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        raise ValueError("DEEPSEEK_API_KEY_MISSING")

    try:
        read_sparse_page(once)
    except ValueError as exc:
        assert str(exc) == "DEEPSEEK_API_KEY_MISSING"
    else:
        raise AssertionError("expected ValueError")
    assert calls["n"] == 1


def test_read_sparse_page_reraises_model_without_image_support():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        raise RuntimeError("This model does not support image input")

    try:
        read_sparse_page(once)
    except RuntimeError as exc:
        assert "does not support image" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    assert calls["n"] == 1


def test_read_sparse_page_scraps_after_three_failures():
    calls = {"n": 0}

    def once() -> str:
        calls["n"] += 1
        return ""

    assert read_sparse_page(once) is None
    assert calls["n"] == MAX_VISION_ATTEMPTS


def test_empty_paper_message_has_no_secrets():
    assert EMPTY_PAPER_MESSAGE == "这些页无法识别，请换清晰件再交。"
    assert "技术说明" not in EMPTY_PAPER_MESSAGE
    assert "连接超时建议重试" not in EMPTY_PAPER_MESSAGE
