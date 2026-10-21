from app.services.practice_fill import needs_figure


def test_needs_figure_matches_diagram_topics_not_the_bare_word_function():
    assert needs_figure("几何", ["求阴影部分面积"]) is True
    assert needs_figure("二次函数", ["画出函数图像"]) is True
    assert needs_figure("欧姆定律", ["画出电路"]) is True
    assert needs_figure("实验室制氧", ["画出化学装置"]) is True
    assert needs_figure("一次函数", ["求解析式"]) is False
    assert needs_figure("牛顿第一定律", ["用文字说明惯性"]) is False


def test_practice_outcome_retries_blank_and_missing_figure_only():
    from app.services.practice_fill import practice_outcome

    assert practice_outcome("几何", ["求面积"], ["geometry"], [False]) == "store"
    assert practice_outcome("几何", ["求面积"], ["none"], [False]) == "retry"
    assert practice_outcome("一次函数", ["求解析式"], ["none"], [False]) == "store"
    assert practice_outcome("概念", ["", "  "], ["none"], [False]) == "retry"
    assert practice_outcome("电路", [""], ["none"], [True]) == "store"


def test_fill_skips_stored_points_and_timeout_keeps_them():
    from app.services.llm_errors import tool_error_user_text
    from app.services.practice_fill import TIMEOUT_MESSAGE, PracticeFillTimeout, fill_practice_pdfs

    points = [("kp_a", "一次函数"), ("kp_b", "几何")]
    calls: list[str] = []

    def generate_one(key: str, name: str):
        calls.append(key)
        if key == "kp_b":
            raise PracticeFillTimeout(["kp_a"])
        return ("store", key)

    try:
        fill_practice_pdfs(points, stored_keys=["kp_a"], generate_one=generate_one)
        raised = False
    except PracticeFillTimeout as exc:
        raised = True
        assert exc.stored_keys == ["kp_a"]
    assert raised is True
    assert calls == ["kp_b"]
    assert tool_error_user_text("", PracticeFillTimeout(["kp_a"])) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE


def test_generate_one_for_tool_does_not_store_a_retry(monkeypatch):
    from app.services.practice_fill import generate_one_for_tool

    stored: list[str] = []

    def draft(key: str, name: str):
        return (["画出函数图像"], ["none"], [False], {"key": key})

    def store(payload: dict):
        stored.append(payload["key"])

    action, key = generate_one_for_tool(
        "kp_plot",
        "二次函数",
        draft=draft,
        store=store,
    )
    assert action == "retry"
    assert stored == []
    assert key == "kp_plot"
