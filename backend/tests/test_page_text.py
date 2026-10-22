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
