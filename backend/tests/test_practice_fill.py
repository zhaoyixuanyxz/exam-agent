from app.services.practice_fill import needs_figure


def test_needs_figure_matches_diagram_topics_not_the_bare_word_function():
    assert needs_figure("几何", ["求阴影部分面积"]) is True
    assert needs_figure("二次函数", ["画出函数图像"]) is True
    assert needs_figure("欧姆定律", ["画出电路"]) is True
    assert needs_figure("实验室制氧", ["画出化学装置"]) is True
    assert needs_figure("一次函数", ["求解析式"]) is False
    assert needs_figure("牛顿第一定律", ["用文字说明惯性"]) is False
    assert needs_figure("函数", ["观察函数图象"]) is True
    assert needs_figure("一次函数的图象", ["求交点"]) is True
    assert needs_figure("二次函数的图象与性质", ["开口方向"]) is True


def test_practice_outcome_retries_blank_and_missing_figure_only():
    from app.services.practice_fill import practice_outcome

    assert practice_outcome("几何", ["求面积"], ["geometry"], [False]) == "store"
    assert practice_outcome("几何", ["求面积"], ["none"], [False]) == "retry"
    assert practice_outcome("一次函数", ["求解析式"], ["none"], [False]) == "store"
    assert practice_outcome("概念", ["", "  "], ["none"], [False]) == "retry"
    assert practice_outcome("电路", [""], ["none"], [True]) == "store"
    assert (
        practice_outcome("几何", ["求面积"], ["none"], [False], include_figures=False)
        == "store"
    )


def test_fill_abandons_point_after_retry_cap_without_blocking_later_points():
    from app.services.practice_fill import MAX_RETRIES_PER_POINT, fill_practice_pdfs

    points = [("kp_bad", "几何"), ("kp_ok", "一次函数")]
    calls: list[str] = []

    def generate_one(key: str, name: str):
        calls.append(key)
        if key == "kp_bad":
            return ("retry", key)
        return ("store", key)

    stored = fill_practice_pdfs(points, stored_keys=[], generate_one=generate_one)
    assert stored == ["kp_ok"]
    assert calls.count("kp_bad") == MAX_RETRIES_PER_POINT
    assert "kp_ok" in calls


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


def test_fill_keeps_points_stored_before_a_later_timeout():
    from app.services.practice_fill import PracticeFillTimeout, fill_practice_pdfs

    points = [("kp_a", "一次函数"), ("kp_b", "几何"), ("kp_c", "电路")]

    def generate_one(key: str, name: str):
        if key == "kp_b":
            return ("store", "kp_b")
        if key == "kp_c":
            raise PracticeFillTimeout(["ignored"])
        return ("store", key)

    try:
        fill_practice_pdfs(points, stored_keys=["kp_a"], generate_one=generate_one)
        raised = False
    except PracticeFillTimeout as exc:
        raised = True
        assert exc.stored_keys == ["kp_a", "kp_b"]
    assert raised is True


def test_draft_is_connection_timeout_treats_interrupts_like_timeout():
    from app.agent.tools import _draft_is_connection_timeout

    assert _draft_is_connection_timeout(TimeoutError()) is True
    assert _draft_is_connection_timeout(ConnectionResetError()) is True
    assert _draft_is_connection_timeout(ConnectionError("Connection refused")) is True
    assert _draft_is_connection_timeout(ValueError("nope")) is False


def test_generate_one_for_tool_does_not_store_a_retry():
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
